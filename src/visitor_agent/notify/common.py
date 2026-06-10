"""Shared formatting for the guard notification card, channel-agnostic."""

from __future__ import annotations


def visitor_rows(visit: dict) -> list[tuple[str, str]]:
    return [
        ("车牌号", visit.get("plate") or "—"),
        ("来访单位", visit.get("company") or "—"),
        ("来访事由", visit.get("reason") or "—"),
        ("手机号", visit.get("phone") or "—"),
        ("入场时间", visit.get("entry_time") or "—"),
    ]


def is_returning(visit: dict) -> bool:
    return bool(visit.get("returning"))


def title(visit: dict) -> str:
    return "🚗 访客登记" + ("（回访车辆）" if is_returning(visit) else "")
