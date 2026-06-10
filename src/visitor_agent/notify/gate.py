"""Gate barrier control — STUBBED for the demo.

In production this would call the Hikvision (海康威视) barrier controller on the
site LAN. The realistic integration is an ISAPI HTTP request with digest auth:

    PUT http://<controller-ip>/ISAPI/ITC/Entrance/barrierGateCtrl/channels/1
        <BarrierGate><cmd>open</cmd></BarrierGate>

That controller lives on the private site network, not the public internet, so
it cannot be exercised from a developer's laptop. For the demo we log the intent
and return success; the answer at the interview is "this is one HTTP call away."
"""

from __future__ import annotations

import logging

logger = logging.getLogger("visitor_agent.gate")


def open_gate(visit_id: int | None = None, plate: str | None = None) -> bool:
    """Pretend to raise the barrier. Returns True (always succeeds in demo)."""
    logger.info("GATE OPEN command sent | visit_id=%s plate=%s", visit_id, plate)
    print(f"[GATE] 已发送抬杆指令 (open) | visit_id={visit_id} plate={plate}")
    return True


def isapi_barrier_payload() -> tuple[str, str]:
    """The real ISAPI call shape, kept here as living documentation."""
    path = "/ISAPI/ITC/Entrance/barrierGateCtrl/channels/1"
    body = "<BarrierGate><cmd>open</cmd></BarrierGate>"
    return path, body
