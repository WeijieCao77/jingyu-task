"""Guard takeover decisions made on the phone keypad (DTMF) during a live call.

After the guard is dialed/joined into the call, they press a key to decide:
  1 → 放行 (open the gate + record released)
  2 → 拒绝 (record denied; gate stays down)

`release()` confirms the visit the AI already created (LiveNotifier.last_visit_id)
if there is one, otherwise creates a confirmed visit from whatever info was
collected so far — so a takeover that happens mid-registration still opens the
gate and shows up on the dashboard. Pure DB + gate, so it's unit-testable.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger("visitor_agent.takeover")


def release(info: dict, last_visit_id: int | None = None,
            tz: str = "Asia/Shanghai") -> int | None:
    """Open the gate for this car and mark it released. Returns the visit id."""
    from .db import repo
    from .notify import gate

    repo.init_db()
    if last_visit_id:
        repo.mark_confirmed_by_id(last_visit_id)
        visit = repo.get_visit_by_id(last_visit_id)
    else:
        data = dict(info)
        if not data.get("entry_time"):
            data["entry_time"] = datetime.now(ZoneInfo(tz)).strftime("%Y-%m-%d %H:%M")
        visit = repo.create_visit(data, confirm_token=secrets.token_urlsafe(16), status="pending")
        repo.mark_confirmed_by_id(visit.id)
    if visit is None:
        return None
    gate.open_gate(visit_id=visit.id, plate=visit.plate)
    cid = f"visit-{visit.id}"
    repo.log_event(cid, "confirmed", text=f"门卫电话放行 {visit.plate or ''}")
    repo.log_event(cid, "gate", text="已发送抬杆指令 (电话按键)")
    return visit.id


def deny(info: dict) -> None:
    """Record that the guard refused entry on the keypad (gate stays down)."""
    from .db import repo

    repo.init_db()
    repo.log_event("guard-deny", "escalation",
                   text=f"门卫电话拒绝放行 {info.get('plate') or ''}")
