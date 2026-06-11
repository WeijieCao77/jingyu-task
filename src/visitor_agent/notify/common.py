"""Shared formatting for the guard notification card, channel-agnostic."""

from __future__ import annotations


def visitor_rows(visit: dict) -> list[tuple[str, str]]:
    rows = [
        ("车牌号", visit.get("plate") or "—"),
        ("来访单位", visit.get("company") or "—"),
        ("来访事由", visit.get("reason") or "—"),
        ("手机号", visit.get("phone") or "—"),
    ]
    if visit.get("name"):
        rows.append(("姓名", visit["name"]))
    rows.append(("入场时间", visit.get("entry_time") or "—"))
    return rows


def is_returning(visit: dict) -> bool:
    return bool(visit.get("returning"))


def status_lines(visit: dict) -> list[str]:
    """Extra highlight lines the guard must see: access status + returning info.

    Access first (more urgent than a returning flag). Falls back to a bare label
    if only the raw status/flag is present (e.g. read from the DB row)."""
    lines: list[str] = []
    if visit.get("access_summary"):
        lines.append(visit["access_summary"])
    elif visit.get("access_status") == "blacklist":
        lines.append("⛔ 黑名单")
    elif visit.get("access_status") == "whitelist":
        lines.append("✅ 白名单")
    if visit.get("returning_summary"):
        lines.append("🔁 " + visit["returning_summary"])
    elif is_returning(visit):
        lines.append("🔁 老访客")
    return lines


def title(visit: dict) -> str:
    """Card title — loudly prefixed for an access hit so the guard can't miss it."""
    base = "🚗 访客登记"
    if visit.get("access_status") == "blacklist":
        return "⛔ 黑名单访客 · " + base
    if visit.get("access_status") == "whitelist":
        return "✅ 白名单访客 · " + base
    return base + ("（回访车辆）" if is_returning(visit) else "")
