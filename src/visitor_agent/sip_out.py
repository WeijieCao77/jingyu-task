"""Outbound SIP: dial the guard's phone and bridge them into a live call (转人工).

When a call needs a human, instead of the guard opening a browser, we add the
guard as a SIP participant in the *same* LiveKit room: their phone rings, they
answer, and — because the participant identity starts with "guard" — the AI
yields (see agent.py participant_connected). No browser / mic permission needed;
the guard talks on a normal phone.

Requires a LiveKit *outbound* SIP trunk (SIP_OUTBOUND_TRUNK_ID) + the guard's
number (GUARD_DIAL_NUMBER). No-op (returns False) if unconfigured or LiveKit
isn't reachable — must never break the call.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("visitor_agent.sip_out")


async def dial_guard(cfg, room_name: str, number: str | None = None) -> bool:
    """Ring the guard and join them to `room_name`. Returns True if the dial was
    requested. `number` overrides cfg.guard_dial_number (e.g. a chosen guard)."""
    number = (number or cfg.guard_dial_number or "").strip()
    trunk = (cfg.sip_outbound_trunk_id or "").strip()
    if not (number and trunk and room_name):
        return False
    if not (cfg.livekit_url and cfg.livekit_api_key and cfg.livekit_api_secret):
        return False
    try:
        from livekit import api

        host = cfg.livekit_url.replace("wss://", "https://").replace("ws://", "http://")
        lkapi = api.LiveKitAPI(host, cfg.livekit_api_key, cfg.livekit_api_secret)
        try:
            await lkapi.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    sip_trunk_id=trunk,
                    sip_call_to=number,
                    room_name=room_name,
                    participant_identity="guard-phone",
                    participant_name="门卫",
                )
            )
            logger.info("dialed guard %s into room %s", number, room_name)
            return True
        finally:
            await lkapi.aclose()
    except Exception:  # noqa: BLE001 — never break the call
        logger.exception("dial guard failed")
        return False
