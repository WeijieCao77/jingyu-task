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
import time

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

    def __init__(self, reg: RegistrationSession, on_escalate=None) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)
        self._reg = reg
        self._on_escalate = on_escalate  # async cb(reason) → push alert to guard

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
        result = self._reg.request_human(reason=reason)
        if self._on_escalate:
            try:
                await self._on_escalate(reason)  # also ping the guard's phone
            except Exception:  # noqa: BLE001
                logger.exception("escalation alert error")
        return result


class GuardQueryAgent(Agent):
    """Voice data assistant for a guard who CALLS IN to query (caller-id on the
    GUARD_PHONES whitelist). Exposes the same safe, read-only tools as the
    text/console guard agent — the LLM picks a tool and voices the answer. No
    registration, no gate; a guard can't accidentally register a visitor."""

    def __init__(self) -> None:
        from .guard_query import _system_prompt

        super().__init__(
            instructions=_system_prompt(get_settings())
            + " 这是电话语音对话，请用简短中文口语回答，数字念清楚，必要时主动追问澄清。"
        )

    @function_tool()
    async def count_visits(
        self, context: RunContext,  # noqa: ARG002
        since_iso: str | None = None, until_iso: str | None = None,
        company: str | None = None, status: str | None = None,
    ) -> str:
        """统计访问车辆数。可按时间(ISO8601)、来访单位、放行状态过滤；
        status：confirmed=已放行 / pending=待核对 / 空=全部。"""
        from .guard_query import run_tool

        return run_tool("count_visits", {"since_iso": since_iso, "until_iso": until_iso,
                                         "company": company, "status": status})

    @function_tool()
    async def list_visits(
        self, context: RunContext,  # noqa: ARG002
        plate: str | None = None, phone: str | None = None,
        company: str | None = None, limit: int | None = None,
    ) -> str:
        """按车牌/手机号/来访单位列出访问记录（最近优先）。"""
        from .guard_query import run_tool

        return run_tool("list_visits", {"plate": plate, "phone": phone,
                                        "company": company, "limit": limit})

    @function_tool()
    async def busiest_hours(
        self, context: RunContext, since_iso: str | None = None  # noqa: ARG002
    ) -> str:
        """各小时(0-23)的访问次数直方图，判断高峰时段。"""
        from .guard_query import run_tool

        return run_tool("busiest_hours", {"since_iso": since_iso})

    @function_tool()
    async def frequent_visitors(
        self, context: RunContext,  # noqa: ARG002
        min_visits: int | None = None, limit: int | None = None,
    ) -> str:
        """常客名单/访客画像（按人聚合）：次数、车牌、常去单位、姓名、最近一次。"""
        from .guard_query import run_tool

        return run_tool("frequent_visitors", {"min_visits": min_visits, "limit": limit})


async def _decide_guard(ctx: JobContext, cfg) -> bool:
    """True if the caller's number is on GUARD_PHONES → route to the voice data
    assistant instead of visitor registration. Only consulted when GUARD_PHONES
    is set, so the default (no whitelist) leaves every call as a visitor — zero
    behaviour change. Waits briefly for the caller participant to appear."""
    from .slots import normalize_phone

    guard_set = {normalize_phone(x) for x in cfg.guard_phones.split(",") if x.strip()}
    guard_set.discard(None)
    if not guard_set:
        return False
    for _ in range(20):  # up to ~2s
        parts = list(getattr(ctx.room, "remote_participants", {}).values())
        if parts:
            for p in parts:
                num = (getattr(p, "attributes", None) or {}).get("sip.phoneNumber")
                if num and normalize_phone(num) in guard_set:
                    return True
            return False  # a caller is present but not a whitelisted guard
        await asyncio.sleep(0.1)
    return False


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

    # A whitelisted guard phoning in goes to the voice DATA assistant (query),
    # not visitor registration. Default (no GUARD_PHONES) → always a visitor.
    is_guard = await _decide_guard(ctx, cfg) if cfg.guard_phones else False

    if is_guard:
        sink("call_started", None, f"门卫数据查询来电（{call_id}）", None)
        logger.info("guard data-query caller")
        reg = None
        agent = GuardQueryAgent()
    else:
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

        async def _on_escalate(reason) -> None:  # noqa: ANN001
            from .notify import dispatch

            base = cfg.public_base_url.rstrip("/")
            link = f"{base}/guard_call?room={ctx.room.name}"
            txt = (f"⚠️ 访客请求转人工{('：' + reason) if reason else ''}\n"
                   f"房间：{ctx.room.name}\n介入：{link}")
            await dispatch.push_alert(cfg, txt)

        agent = VisitorAgent(reg, on_escalate=_on_escalate)

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

    last_user = [time.monotonic()]  # last visitor utterance time (idle watchdog)

    # Stream the live transcript to the dashboard (both visitor + guard-query).
    @session.on("conversation_item_added")
    def _on_item(ev) -> None:  # noqa: ANN001
        try:
            item = ev.item
            role = getattr(item, "role", None)
            text = getattr(item, "text_content", None)
            if role == "user":
                last_user[0] = time.monotonic()
            if role in ("user", "assistant") and text:
                sink("user" if role == "user" else "agent", role, text, None)
        except Exception:  # noqa: BLE001
            logger.exception("transcript log error")

    # --- visitor-only wiring (skipped for a guard data-query call) ---
    if not is_guard:
        def _prefill_caller_phone(participant) -> None:  # noqa: ANN001
            """For a SIP/phone call the dialing number IS the visitor's mobile —
            use caller-ID as the phone so we don't ask or risk mis-hearing it (and
            returning + blacklist/whitelist checks fire immediately)."""
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

        # Gate approved (FR-2): web confirm sends {"type":"approved"} → AI tells
        # the visitor. Best-effort — the visitor may already have hung up.
        @ctx.room.on("data_received")
        def _on_data(*args) -> None:  # noqa: ANN002 — sig varies by livekit version
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

        # Human takeover: a guard joining (identity 'guard*') makes the AI hand off.
        @ctx.room.on("participant_connected")
        def _on_participant(participant) -> None:  # noqa: ANN001
            identity = getattr(participant, "identity", "") or ""
            if not identity.startswith("guard"):
                _prefill_caller_phone(participant)  # SIP caller joined → prefill
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

    # Agent speaks first — the 25-second clock starts here. realtime can't say() a
    # fixed string, so _speak() asks the model to voice it; pipeline say()s it.
    greeting = (
        "门卫您好，您想查什么？比如今天放行了多少辆车、最近哪个时段最忙。"
        if is_guard else GREETING
    )
    await _speak(session, cfg, greeting, allow_interruptions=True)

    # FR-4: end the call so the line doesn't stay open. After registration is done
    # (and the AI has said goodbye), hang up on N seconds of visitor silence; a
    # global cap guards against anything stuck open. Guard-query calls only get
    # the global cap. Best-effort — the visitor may have already hung up.
    if not is_guard and (cfg.hangup_silence_sec or cfg.max_call_sec):
        async def _idle_watchdog() -> None:
            t0 = time.monotonic()
            while True:
                await asyncio.sleep(1.0)
                now = time.monotonic()
                if cfg.max_call_sec and now - t0 > cfg.max_call_sec:
                    logger.info("max call duration reached → hang up")
                    break
                if (cfg.hangup_silence_sec and reg.completed
                        and now - last_user[0] > cfg.hangup_silence_sec):
                    logger.info("post-completion silence → hang up")
                    break
            try:
                await session.aclose()
            except Exception:  # noqa: BLE001
                logger.exception("watchdog aclose")
            try:
                await ctx.room.disconnect()
            except Exception:  # noqa: BLE001
                logger.exception("watchdog disconnect")

        asyncio.create_task(_idle_watchdog())


def main() -> None:
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))


if __name__ == "__main__":
    main()
