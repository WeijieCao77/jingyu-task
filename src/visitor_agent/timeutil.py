"""Shared date-range windows.

Both the structured query (/api/query, the 数据库 tab) and the natural-language
guard-query agent must compute 今天/本周/本月 IDENTICALLY — same timezone, same
boundaries — or the two surfaces report different numbers for the same question.
This single helper is the source of truth; both import it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def range_window(range_: str, tz: str):
    """Map today | week | month | all → (since_utc, until_utc) in timezone `tz`.

    `all` (or anything unrecognized) → (None, None) = no time filter. Returned
    bounds are tz-aware UTC so the DB layer compares apples to apples."""
    z = ZoneInfo(tz)
    now = datetime.now(z)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if range_ == "today":
        since = midnight
    elif range_ == "week":
        since = midnight - timedelta(days=now.weekday())
    elif range_ == "month":
        since = midnight.replace(day=1)
    else:
        return None, None
    return since.astimezone(timezone.utc), None
