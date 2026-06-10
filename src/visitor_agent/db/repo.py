"""Thin repository over the Visit table.

A process-wide engine/session factory is created lazily from DATABASE_URL. The
agent process (writer) and the web process (reader/confirmer) both point at the
same database, so a SQLite file works for a single-host demo and a Postgres URL
(e.g. Neon) works for the serverless/multi-host path with zero code change.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import get_settings
from .models import Base, CallEvent, Visit

_engine: Engine | None = None
_Session: sessionmaker[Session] | None = None


def _ensure_sqlite_dir(url: str) -> None:
    prefix = "sqlite:///"
    if url.startswith(prefix):
        path = url[len(prefix):]
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)


def init_db(database_url: str | None = None) -> Engine:
    """Create the engine + tables (idempotent). Safe to call from any process."""
    global _engine, _Session
    url = database_url or get_settings().database_url
    _ensure_sqlite_dir(url)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    _engine = create_engine(url, connect_args=connect_args, future=True)
    _Session = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    Base.metadata.create_all(_engine)
    return _engine


def _session() -> Session:
    if _Session is None:
        init_db()
    assert _Session is not None
    return _Session()


def create_visit(info: dict, confirm_token: str, status: str = "pending") -> Visit:
    with _session() as s:
        visit = Visit(
            plate=info.get("plate"),
            company=info.get("company"),
            reason=info.get("reason"),
            phone=info.get("phone"),
            entry_time=info.get("entry_time"),
            status=status,
            confirm_token=confirm_token,
        )
        s.add(visit)
        s.commit()
        s.refresh(visit)
        return visit


def get_visit_by_token(token: str) -> Visit | None:
    with _session() as s:
        return s.scalar(select(Visit).where(Visit.confirm_token == token))


def mark_confirmed(token: str) -> Visit | None:
    """Idempotently flip a pending visit to confirmed; returns the visit."""
    with _session() as s:
        visit = s.scalar(select(Visit).where(Visit.confirm_token == token))
        if visit is None:
            return None
        if visit.status != "confirmed":
            visit.status = "confirmed"
            visit.confirmed_at = datetime.now(timezone.utc)
            s.commit()
            s.refresh(visit)
        return visit


def find_recent_visit_by_plate(plate: str) -> Visit | None:
    """Most recent prior visit for a plate — powers returning-visitor greetings."""
    if not plate:
        return None
    with _session() as s:
        return s.scalar(
            select(Visit)
            .where(Visit.plate == plate)
            .order_by(Visit.created_at.desc())
        )


# ----- read helpers for the guard query agent -----

def count_visits(since: datetime | None = None, until: datetime | None = None,
                 company: str | None = None) -> int:
    with _session() as s:
        stmt = select(func.count()).select_from(Visit)
        if since is not None:
            stmt = stmt.where(Visit.created_at >= since)
        if until is not None:
            stmt = stmt.where(Visit.created_at <= until)
        if company:
            stmt = stmt.where(Visit.company.like(f"%{company}%"))
        return int(s.scalar(stmt) or 0)


def visits_for(plate: str | None = None, phone: str | None = None,
               company: str | None = None, limit: int = 50) -> list[Visit]:
    with _session() as s:
        stmt = select(Visit)
        if plate:
            stmt = stmt.where(Visit.plate == plate)
        if phone:
            stmt = stmt.where(Visit.phone == phone)
        if company:
            stmt = stmt.where(Visit.company.like(f"%{company}%"))
        stmt = stmt.order_by(Visit.created_at.desc()).limit(limit)
        return list(s.scalars(stmt))


def recent_visits(limit: int = 30) -> list[Visit]:
    with _session() as s:
        return list(
            s.scalars(select(Visit).order_by(Visit.created_at.desc()).limit(limit))
        )


# ----- call events (live dashboard) -----

def log_event(call_id: str, kind: str, role: str | None = None,
              text: str | None = None, payload: str | None = None) -> CallEvent:
    with _session() as s:
        ev = CallEvent(call_id=call_id, kind=kind, role=role, text=text, payload=payload)
        s.add(ev)
        s.commit()
        s.refresh(ev)
        return ev


def events_after(after_id: int, limit: int = 200) -> list[CallEvent]:
    with _session() as s:
        return list(
            s.scalars(
                select(CallEvent)
                .where(CallEvent.id > after_id)
                .order_by(CallEvent.id)
                .limit(limit)
            )
        )


def latest_event_id() -> int:
    with _session() as s:
        return int(s.scalar(select(func.max(CallEvent.id))) or 0)


def visits_by_hour(since: datetime | None = None) -> dict[int, int]:
    """Histogram of visit counts by hour-of-day (local entry_time string)."""
    counts: dict[int, int] = {}
    with _session() as s:
        stmt = select(Visit.entry_time)
        if since is not None:
            stmt = stmt.where(Visit.created_at >= since)
        for (entry_time,) in s.execute(stmt):
            if entry_time and len(entry_time) >= 16:
                try:
                    hour = int(entry_time[11:13])
                except ValueError:
                    continue
                counts[hour] = counts.get(hour, 0) + 1
    return counts
