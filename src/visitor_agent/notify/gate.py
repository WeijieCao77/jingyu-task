"""Gate barrier control.

Two modes, chosen by config:
  - **Stub (default)**: log "已发送抬杆指令" and succeed. Used for the demo, where
    the barrier controller (on the private site LAN) isn't reachable.
  - **Real Hikvision ISAPI**: if HIKVISION_URL is set, send the actual barrier
    open command over HTTP with digest auth. This is the production path.

The real call shape:
    PUT http://<controller>/ISAPI/ITC/Entrance/barrierGateCtrl/channels/<ch>
        <BarrierGate><cmd>open</cmd></BarrierGate>
"""

from __future__ import annotations

import logging

from ..config import get_settings

logger = logging.getLogger("visitor_agent.gate")


def isapi_barrier_payload(channel: int = 1) -> tuple[str, str]:
    """The real ISAPI call shape (also used by the live call below)."""
    path = f"/ISAPI/ITC/Entrance/barrierGateCtrl/channels/{channel}"
    body = "<BarrierGate><cmd>open</cmd></BarrierGate>"
    return path, body


def _isapi_open(cfg, visit_id, plate) -> bool:
    import httpx

    path, body = isapi_barrier_payload(cfg.hikvision_channel)
    url = cfg.hikvision_url.rstrip("/") + path
    try:
        auth = httpx.DigestAuth(cfg.hikvision_user, cfg.hikvision_password)
        with httpx.Client(timeout=5.0) as client:
            resp = client.put(url, content=body, auth=auth)
        ok = resp.status_code in (200, 204)
        logger.info("ISAPI gate open -> %s (visit=%s plate=%s)", resp.status_code, visit_id, plate)
        print(f"[GATE] 海康 ISAPI 抬杆 {'成功' if ok else '失败'} (HTTP {resp.status_code}) plate={plate}")
        return ok
    except Exception as exc:  # noqa: BLE001 — never break the confirm flow
        logger.exception("ISAPI gate error: %s", exc)
        print(f"[GATE] 海康 ISAPI 调用异常：{exc}")
        return False


def open_gate(visit_id: int | None = None, plate: str | None = None) -> bool:
    """Raise the barrier. Real ISAPI if configured, else stub (always True)."""
    cfg = get_settings()
    if cfg.hikvision_url:
        return _isapi_open(cfg, visit_id, plate)
    logger.info("GATE OPEN command sent (stub) | visit_id=%s plate=%s", visit_id, plate)
    print(f"[GATE] 已发送抬杆指令 (stub) | visit_id={visit_id} plate={plate}")
    return True
