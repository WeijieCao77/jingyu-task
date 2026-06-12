"""LiveKit Agents worker — the telephony entry point.

A Twilio phone number routes inbound calls (via SIP) into a LiveKit room; this
worker is dispatched per call, so each call gets its own RegistrationSession and
the design is naturally concurrent (multiple cars calling at once = multiple
independent jobs, no shared mutable state).

Run:  python -m visitor_agent.agent dev      # local dev (hot reload)
      python -m visitor_agent.agent start     # production worker
"""

from __future__ import annotations

import asyncio
import json
import logging

from dotenv import load_dotenv

# LiveKit's worker reads LIVEKIT_URL / API_KEY / SECRET (and plugin keys) from
# os.environ — pydantic reading .env does NOT export them, so load .env into the
# process environment here or the worker fails to connect.
load_dotenv()

from livekit.agents import (  # noqa: E402
    Agent,
    AgentSession,
    JobContext,
    RunContext,
    WorkerOptions,
    cli,
    function_tool,
)

# Register default plugins at module import (= main thread). Job workers are
# spawned (not forked) on Windows, so a lazy `from livekit.plugins import ...`
# inside the entrypoint would run on a worker *thread* and raise
# "Plugins must be registered on the main thread", crashing every call. Importing
# here registers on the main thread; providers.py's lazy imports become no-ops.
# Optional providers (deepgram/azure) stay lazy and self-register when selected.
from livekit.plugins import anthropic as _anthropic  # noqa: E402,F401
from livekit.plugins import openai as _openai  # noqa: E402,F401
from livekit.plugins import silero as _silero  # noqa: E402,F401

from .config import get_settings
from .db import repo
from .prompts import GREETING, SYSTEM_PROMPT
from .providers import (
    build_llm,
    build_realtime,
    build_stt,
    build_tts,
    build_turn_detection,
    build_vad,
)
from .session_logic import LiveNotifier, RegistrationSession, make_db_lookup

logger = logging.getLogger("visitor_agent.agent")


async def _speak(session, cfg, text: str, *, allow_interruptions: bool = True) -> None:
    """Speak a line regardless of voice mode.

    Realtime (speech-to-speech) has no standalone TTS and can't `say()` a fixed
    string — calling it raises RuntimeError and crashes the job — so we ask the
    model to voice the line instead. Pipeline keeps the deterministic `say()`.
    """
    if cfg.voice_mode == "realtime":
        await session.generate_reply(
            instructions=f"用自然的中文普通话对访客说这句话（可润色语气，但保持原意）：{text}"
        )
    else:
        await session.say(text, allow_interruptions=allow_interruptions)


class VisitorAgent(Agent):
    """The gatekeeper persona, exposing two tools the LLM calls to fill slots."""

    def __init__(self, reg: RegistrationSession) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)
        self._reg = reg

    @function_tool()
    async def record_visitor_info(
        self,
        context: RunContext,  # noqa: ARG002 — required by the tool signature
        plate: str | None = None,
        company: str | None = None,
        reason: str | None = None,
        phone: str | None = None,
        name: str | None = None,
    ) -> str:
        """记录访客信息（可增量、可多次调用）。听到任何一项就立刻调用。

        Args:
            plate: 车牌号，如 沪A12345（原样传入即可）
            company: 来访单位 / 找的公司
            reason: 来访事由，如 送货、拜访、面试
            phone: 手机号（原样传入即可）
            name: 访客称呼/姓名（如"张师傅"，对方提到才填，可选）
        """
        return self._reg.record(
            plate=plate, company=company, reason=reason, phone=phone, name=name
        )

    @function_tool()
    async def complete_registration(self, context: RunContext) -> str:  # noqa: ARG002
        """四项信息齐全后调用：完成登记、记录入场时间、推送门卫微信。"""
        return await self._reg.complete()

    @function_tool()
    async def request_human(
        self, context: RunContext, reason: str | None = None  # noqa: ARG002
    ) -> str:
        """转人工：访客要求真人、或你听不懂/情况异常时调用，通知保安介入。

        Args:
            reason: 转人工的简短原因（如"访客要求真人""听不清"）
        """
        return self._reg.request_human(reason=reason)


def _make_event_sink(call_id: str):
    """Persist dashboard events; never let a logging error break the call."""

    def sink(kind: str, role: str | None, text: str | None, payload: dict | None) -> None:
        try:
            repo.log_event(
                call_id=call_id,
                kind=kind,
                role=role,
                text=text,
                payload=json.dumps(payload, ensure_ascii=False) if payload else None,
            )
        except Exception:  # noqa: BLE001
            logger.exception("failed to log event")

    return sink


async def entrypoint(ctx: JobContext) -> None:
    cfg = get_settings()
    repo.init_db(cfg.database_url)

    await ctx.connect()

    call_id = ctx.room.name or "call"
    sink = _make_event_sink(call_id)
    sink("call_started", None, f"来电接入（{call_id}）", None)

    from .access import make_access_checker
    from .roster import make_matcher

    reg = RegistrationSession(
        notifier=LiveNotifier(cfg, room=ctx.room.name),
        lookup_returning=make_db_lookup(),
        tz=cfg.timezone,
        event_sink=sink,
        roster_match=make_matcher(cfg.roster_path, cfg.roster_threshold),
        access_check=make_access_checker(cfg.access_list_path),
    )
    agent = VisitorAgent(reg)

    if cfg.voice_mode == "realtime":
        # Speech-to-speech: one realtime model replaces STT+LLM+TTS (lowest
        # latency; turn detection runs server-side). The roster / returning /
        # slot-filling logic lives in session_logic and is voice-mode-independent,
        # so it keeps working unchanged here.
        logger.info("voice_mode=realtime (speech-to-speech)")
        session = AgentSession(llm=build_realtime(cfg))
    else:
        # Pipeline STT→LLM→TTS. Turn detection improves barge-in naturalness but
        # needs a model file. If it isn't available, fall back to VAD-only
        # endpointing so the call still works — "directly usable" beats "perfect".
        try:
            turn_detection = build_turn_detection()
        except Exception as exc:  # noqa: BLE001
            logger.warning("turn detector unavailable, using VAD only: %s", exc)
            turn_detection = None

        session = AgentSession(
            stt=build_stt(cfg),
            llm=build_llm(cfg),
            tts=build_tts(cfg),
            vad=build_vad(cfg),
            turn_detection=turn_detection,
            # Latency: start generating before the caller fully finishes + reply
            # sooner after they stop. Tunable via env (see config.py).
            preemptive_generation=cfg.preemptive_generation,
            min_endpointing_delay=cfg.min_endpointing_delay,
        )

    def _prefill_caller_phone(participant) -> None:  # noqa: ANN001
        """For a SIP/phone call the dialing number IS the visitor's mobile — use
        the caller-ID as the phone so we don't have to ask or risk mis-hearing it
        (and returning-visitor + blacklist/whitelist checks fire immediately)."""
        try:
            attrs = getattr(participant, "attributes", None) or {}
            num = attrs.get("sip.phoneNumber") or attrs.get("sip.from")
            if not num or reg.info.phone:
                return
            from .slots import normalize_phone

            phone = normalize_phone(num)
            if phone:
                reg.record(phone=phone)
                sink("slot", None, f"主叫号码已预填手机：{phone}", reg.info.to_dict())
                logger.info("prefilled visitor phone from SIP caller id")
        except Exception:  # noqa: BLE001
            logger.exception("caller-id prefill error")

    # A SIP caller may already be in the room at entrypoint — prefill now.
    for _p in list(getattr(ctx.room, "remote_participants", {}).values()):
        _prefill_caller_phone(_p)

    # Stream the live transcript to the dashboard (final turns only).
    @session.on("conversation_item_added")
    def _on_item(ev) -> None:  # noqa: ANN001
        try:
            item = ev.item
            role = getattr(item, "role", None)
            text = getattr(item, "text_content", None)
            if role in ("user", "assistant") and text:
                sink("user" if role == "user" else "agent", role, text, None)
        except Exception:  # noqa: BLE001
            logger.exception("transcript log error")

    # Gate approved (FR-2): the web confirm handler sends a {"type":"approved"}
    # data message to this room when the guard releases the barrier. The AI then
    # tells the visitor it's done — closing the loop on the live call. Best-effort:
    # the visitor may already have hung up.
    @ctx.room.on("data_received")
    def _on_data(*args) -> None:  # noqa: ANN002 — sig varies by livekit version
        # 1.x emits a single DataPacket; older emits (data, participant, ...).
        # args[0] is the packet/bytes either way; .data unwraps a DataPacket.
        try:
            packet = args[0] if args else None
            raw = getattr(packet, "data", packet)
            msg = json.loads(bytes(raw).decode("utf-8"))
        except Exception:  # noqa: BLE001
            return
        if msg.get("type") != "approved":
            return
        sink("approved", None, "保安已放行，AI 通知访客", None)

        async def _announce() -> None:
            try:
                await _speak(session, cfg, "好的，已经为您放行，请进，栏杆已经抬起，祝您一路顺利！")
            except Exception:  # noqa: BLE001
                logger.exception("approved announce error")

        asyncio.create_task(_announce())

    # Human takeover: when a guard joins the same room (identity starts with
    # "guard"), the AI hands off — says a short line, then leaves the room so the
    # guard and visitor talk directly. Works for browser/QR and phone alike,
    # because all access modes share one LiveKit room.
    @ctx.room.on("participant_connected")
    def _on_participant(participant) -> None:  # noqa: ANN001
        identity = getattr(participant, "identity", "") or ""
        if not identity.startswith("guard"):
            _prefill_caller_phone(participant)  # SIP caller joined → prefill phone
            return
        sink("human_joined", None, f"保安已接入通话（{identity}）", None)

        async def _handoff() -> None:
            try:
                await _speak(session, cfg, "门卫师傅来了，由他来跟您说，再见。",
                             allow_interruptions=False)
            except Exception:  # noqa: BLE001
                logger.exception("handoff say error")
            finally:
                try:
                    await session.aclose()  # AI leaves; guard + visitor remain
                except Exception:  # noqa: BLE001
                    logger.exception("handoff aclose error")

        asyncio.create_task(_handoff())

    await session.start(agent=agent, room=ctx.room)

    # Agent speaks first — this is when the 25-second clock starts. In realtime
    # mode there's no standalone TTS to say() a fixed string, so _speak() asks the
    # model to voice the greeting instead (pipeline still say()s it verbatim).
    await _speak(session, cfg, GREETING, allow_interruptions=True)


def main() -> None:
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))


if __name__ == "__main__":
    main()
