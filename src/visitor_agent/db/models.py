"""SQLAlchemy models. One table — `visits` — is enough for v1 plus the bonus
returning-visitor and guard-query features."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    plate: Mapped[str | None] = mapped_column(String(16), index=True)
    company: Mapped[str | None] = mapped_column(String(128))
    reason: Mapped[str | None] = mapped_column(String(128))
    phone: Mapped[str | None] = mapped_column(String(20), index=True)

    # "YYYY-MM-DD HH:MM" in the configured local timezone (human-facing).
    entry_time: Mapped[str | None] = mapped_column(String(32))

    # pending -> confirmed (guard tapped the link) -> (gate stub fired)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)

    # Random urlsafe token the guard's confirm link carries.
    confirm_token: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    notes: Mapped[str | None] = mapped_column(Text)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "plate": self.plate,
            "company": self.company,
            "reason": self.reason,
            "phone": self.phone,
            "entry_time": self.entry_time,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
        }
