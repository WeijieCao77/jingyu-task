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

    if url.startswith("sqlite"):
        # WAL lets the agent (writer) and web (reader/writer) hit the same file
        # concurrently without "database is locked"; busy_timeout adds patience.
        from sqlalchemy import event

        @event.listens_for(_engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=5000")
            cur.close()

    _Session = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    Base.metadata.create_all(_engine)
    _ensure_columns(_engine)
    return _engine


# New nullable columns added after a DB may already exist. create_all() never
# ALTERs an existing table, so a demo SQLite file (or a live Postgres) would
# otherwise raise "no such column". Add them additively, idempotently.
_ADDED_COLUMNS = {"access_status": "VARCHAR(16)", "room": "VARCHAR(64)"}


def _ensure_columns(engine: Engine) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "visits" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("visits")}
    with engine.begin() as conn:
        for col, ddl in _ADDED_COLUMNS.items():
            if col not in existing:
                conn.execute(text(f"ALTER TABLE visits ADD COLUMN {col} {ddl}"))


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
            name=info.get("name"),
            entry_time=info.get("entry_time"),
            status=status,
            access_status=info.get("access_status"),
            room=info.get("room"),
            confirm_token=confirm_token,
        )
        s.add(visit)
        s.commit()
        s.refresh(visit)
        return visit


def get_visit_by_token(token: str) -> Visit | None:
    with _session() as s:
        return s.scalar(select(Visit).where(Visit.confirm_token == token))


def get_visit_by_id(visit_id: int) -> Visit | None:
    with _session() as s:
        return s.get(Visit, visit_id)


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


def mark_confirmed_by_id(visit_id: int) -> Visit | None:
    """Confirm a visit from the local guard console (Dashboard button)."""
    with _session() as s:
        visit = s.get(Visit, visit_id)
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


def _profile(match_type: str, visit_count: int, v: Visit) -> dict:
    return {
        "match_type": match_type,          # plate+phone | phone | plate
        "visit_count": visit_count,
        "name": v.name,
        "last_company": v.company,
        "last_reason": v.reason,
        "last_time": v.entry_time
        or (v.created_at.isoformat() if v.created_at else None),
    }


def recognize(plate: str | None = None, phone: str | None = None) -> dict | None:
    """Comprehensive returning-customer recognition.

    Phone identifies the *person* (stable across vehicles); plate identifies the
    *vehicle* (may have different drivers). We return a profile with the match
    basis, lifetime visit count, name, and last visit — so the agent can choose
    how confidently to greet (recognised person vs only-recognised vehicle).
    """
    with _session() as s:
        phone_hits: list[Visit] = []
        plate_hits: list[Visit] = []
        if phone:
            phone_hits = list(
                s.scalars(
                    select(Visit).where(Visit.phone == phone).order_by(Visit.created_at.desc())
                )
            )
        if plate:
            plate_hits = list(
                s.scalars(
                    select(Visit).where(Visit.plate == plate).order_by(Visit.created_at.desc())
                )
            )
        if phone and phone_hits:
            same_vehicle = bool(plate) and any(v.plate == plate for v in phone_hits)
            mt = "plate+phone" if same_vehicle else "phone"
            return _profile(mt, len(phone_hits), phone_hits[0])
        if plate and plate_hits:
            return _profile("plate", len(plate_hits), plate_hits[0])
        return None


def find_recent_visit(plate: str | None = None, phone: str | None = None) -> Visit | None:
    """Most recent prior visit matching plate OR phone — returning-customer lookup.

    Plate is tried first (it's known earliest in the call); phone is the fallback
    so a returning driver in a different car is still recognised."""
    with _session() as s:
        if plate:
            hit = s.scalar(
                select(Visit).where(Visit.plate == plate).order_by(Visit.created_at.desc())
            )
            if hit:
                return hit
        if phone:
            return s.scalar(
                select(Visit).where(Visit.phone == phone).order_by(Visit.created_at.desc())
            )
        return None


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


def visitor_profiles(limit: int = 50, min_visits: int = 1) -> list[dict]:
    """Aggregate visit history into per-person profiles (常客名单 / 访客画像).

    Grouped by phone (the person identity); falls back to plate when no phone.
    Returns frequency, the plates/companies seen, last visit, and how many of
    those visits actually opened the gate — feeds the admin view + query agent.
    """
    with _session() as s:
        rows = list(s.scalars(select(Visit).order_by(Visit.created_at.desc())))

    groups: dict[str, dict] = {}
    for v in rows:  # rows are newest-first, so first sighting of a key is latest
        key = v.phone or f"plate:{v.plate or '?'}"
        p = groups.get(key)
        if p is None:
            p = {
                "phone": v.phone, "name": v.name, "plates": set(), "companies": set(),
                "visit_count": 0, "confirmed_count": 0,
                "last_company": v.company, "last_reason": v.reason,
                "last_time": v.entry_time or (v.created_at.isoformat() if v.created_at else None),
            }
            groups[key] = p
        p["visit_count"] += 1
        if v.status == "confirmed":
            p["confirmed_count"] += 1
        if v.plate:
            p["plates"].add(v.plate)
        if v.company:
            p["companies"].add(v.company)
        if not p["name"] and v.name:
            p["name"] = v.name

    profiles = []
    for p in groups.values():
        if p["visit_count"] < min_visits:
            continue
        p["plates"] = sorted(p["plates"])
        p["companies"] = sorted(p["companies"])
        profiles.append(p)
    profiles.sort(key=lambda x: (-x["visit_count"], x.get("phone") or ""))
    return profiles[:limit]


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
