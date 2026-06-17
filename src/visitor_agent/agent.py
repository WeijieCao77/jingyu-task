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
from .prompts import GREETING, GREETING_ASK_PHONE, SYSTEM_PROMPT
from .providers import (
    build_llm,
    build_realtime,
    build_stt,
    build_tts,
    build_turn_detection,
    build_vad,
    realtime_allow_interrupt,
    realtime_server_vad,
)
from .session_logic import LiveNotifier, RegistrationSession, make_db_lookup

logger = logging.getLogger("visitor_agent.agent")


async def _speak(session, cfg, text: str, *, allow_interruptions: bool = True,
                 verbatim: bool = False) -> None:
    """Speak a line regardless of voice mode.

    Realtime (speech-to-speech) has no standalone TTS and can't `say()` a fixed
    string — calling it raises RuntimeError and crashes the job — so we ask the
    model to voice the line instead. `verbatim=True` makes it read the line
    word-for-word (used for the fixed, consistent greeting); otherwise it may
    polish the tone. Pipeline always uses the deterministic `say()`.
    """
    if cfg.voice_mode == "realtime":
        if verbatim:
            instr = (f"严格逐字念出下面这句话，一字不差，不要改写、不要增减、"
                     f"也不要在前后加任何别的话：{text}")
        else:
            instr = f"用自然的中文普通话对访客说这句话（可润色语气，但保持原意）：{text}"
        await session.generate_reply(instructions=instr)
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


async def _sip_attr(ctx: JobContext, key: str) -> str | None:
    """Wait briefly for the SIP participant and return one of its attributes
    (e.g. sip.trunkPhoneNumber = the dialed number, for tenant routing)."""
    for _ in range(15):  # ~1.5s
        for p in list(getattr(ctx.room, "remote_participants", {}).values()):
            v = (getattr(p, "attributes", None) or {}).get(key)
            if v:
                return v
        await asyncio.sleep(0.1)
    return None


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

    # Tell the dashboard when this call ends (any reason: hang up, caller dropped,
    # crash) so the "有访客来电 / 转人工" alert clears instead of lingering.
    async def _on_shutdown(*_a) -> None:  # noqa: ANN002
        try:
            sink("call_ended", None, "通话结束", None)
        except Exception:  # noqa: BLE001
            pass

    ctx.add_shutdown_callback(_on_shutdown)

    # Multi-tenant (opt-in): route this call to its tenant by the DIALED number,
    # so roster/access/notify/guard all use that tenant's config. No-op when
    # TENANTS_PATH is unset → single-tenant behaviour unchanged.
    if cfg.tenants_path:
        try:
            from .tenant import apply_tenant, resolve_tenant

            dialed = await _sip_attr(ctx, "sip.trunkPhoneNumber")
            tenant = resolve_tenant(cfg.tenants_path, dialed)
            if tenant:
                cfg = apply_tenant(cfg, tenant)
                sink("tenant", None, f"租户：{tenant.get('name', '?')}", None)
                logger.info("tenant=%s (dialed %s)", tenant.get("name"), dialed)
        except Exception:  # noqa: BLE001
            logger.exception("tenant resolve error")

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
            from urllib.parse import quote

            from .notify import dispatch

            # Do NOT auto-dial the guard. Send the group an alert with a link; the
            # on-duty guard taps it to CHOOSE to be phoned in (or browser-join) —
            # 经门卫同意后才外呼（用户反馈：转人工不能直接打给门卫）。/takeover 页按
            # TAKEOVER_GUARDS 列出每个门卫，当班的点自己那个才拨。
            base = cfg.public_base_url.rstrip("/")
            link = f"{base}/takeover?room={quote(ctx.room.name, safe='')}"
            if reason:
                link += f"&reason={quote(reason, safe='')}"
            rn = ctx.room.name or ""
            caller = rn.split("_")[1] if rn.startswith("call_") and len(rn.split("_")) > 1 else "—"
            # Markdown card with a tappable button (not a raw URL) — same look as the
            # visitor card; the link opens the takeover page (拨我手机 / 浏览器介入).
            txt = (f"## ⚠️ 访客请求转人工\n"
                   f"> <font color=\"warning\">{reason or '访客要求真人'}</font>\n"
                   f"> **主叫**：{caller}\n\n"
                   f"<font color=\"comment\">———— 请门卫处理 ————</font>\n"
                   f"[【 📞 人工介入 · 选择接听方式 】]({link})")
            await dispatch.push_alert(cfg, txt)

        agent = VisitorAgent(reg, on_escalate=_on_escalate)

    if cfg.voice_mode == "realtime":
        # Speech-to-speech: one realtime model replaces STT+LLM+TTS (lowest
        # latency). The roster / returning / slot-filling logic lives in
        # session_logic and is voice-mode-independent, so it keeps working here.
        logger.info("voice_mode=realtime (speech-to-speech)")
        if realtime_server_vad():
            # LEGACY: OpenAI server-side turn detection. It REQUIRES
            # allow_interruptions=True — passing False raises ValueError and crashes
            # EVERY call at session.start() (true on 1.5.x and 1.6.x). Caveat: on an
            # echoey phone line the AI replies to its own echo (self-talk); prefer
            # the default (client-side VAD) for telephony.
            session = AgentSession(
                llm=build_realtime(cfg),
                allow_interruptions=True,
            )
        else:
            # DEFAULT: local silero VAD drives turns (server VAD disabled in
            # build_realtime). This makes allow_interruptions=False legal, which lets
            # livekit DISCARD inbound audio while the AI speaks — so the AI's own
            # phone echo never becomes a phantom turn (fixes realtime 自说自话). The
            # visitor-turn path still works: silero end-of-turn → commit_audio +
            # generate_reply → reply. REALTIME_ALLOW_INTERRUPT=1 restores barge-in
            # (allow_interruptions=True), at the cost of re-exposing the echo.
            session = AgentSession(
                llm=build_realtime(cfg),
                vad=build_vad(cfg),
                allow_interruptions=realtime_allow_interrupt(),
            )
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
    decided = [False]  # set True once the guard approves/rejects → then we hang up

    # --- Echo guard (realtime + local VAD, no barge-in) ---
    # A phone handset echoes the AI's own voice back into the line. livekit already
    # discards that echo WHILE the AI is speaking (allow_interruptions=False), but
    # the echo TAIL keeps arriving for ~a round-trip AFTER the AI stops — and the
    # local VAD can mishear that tail as a visitor turn, so the AI answers its own
    # echo (the 自说自话 loop; reproduced as residual bursts after the server-VAD
    # fix). So we hold the mic muted through the AI's turn and for a short settle
    # window after it, so the tail is gone before we listen again. Disabled when
    # barge-in is on (REALTIME_ALLOW_INTERRUPT=1) — listening mid-reply is the whole
    # point there — and in pipeline / server-VAD modes.
    _echo_guard = (cfg.voice_mode == "realtime"
                   and not realtime_server_vad()
                   and not realtime_allow_interrupt())
    ears_locked = [False]   # set on human takeover → the guard owns the mic, don't auto-unmute
    _resume_handle = [None]
    if _echo_guard:
        import os as _os

        _settle = max(0.0, float(_os.getenv("REALTIME_ECHO_SETTLE_MS", "600")) / 1000.0)

        def _set_ears(on: bool) -> None:
            try:
                session.input.set_audio_enabled(on)
            except Exception:  # noqa: BLE001
                logger.exception("echo-guard set ears failed")

        @session.on("agent_state_changed")
        def _echo_on_state(ev) -> None:  # noqa: ANN001
            if ears_locked[0]:
                return
            new = getattr(ev, "new_state", None)
            if new == "speaking":
                if _resume_handle[0]:
                    _resume_handle[0].cancel()
                _set_ears(False)
            elif new in ("listening", "idle"):
                if _resume_handle[0]:
                    _resume_handle[0].cancel()

                async def _resume() -> None:
                    try:
                        await asyncio.sleep(_settle)
                        if not ears_locked[0]:
                            _set_ears(True)
                    except asyncio.CancelledError:
                        raise
                    except Exception:  # noqa: BLE001
                        logger.exception("echo-guard resume failed")

                _resume_handle[0] = asyncio.create_task(_resume())

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

        # Announce the guard's decision (confirm/reject) to the visitor, then arm the
        # hang-up. TWO independent triggers funnel through here, idempotent via
        # decided[0] (first wins):
        #   1) DB poll in the idle watchdog — the web /confirm or /reject flips the
        #      visit status in shared Postgres. This is the RELIABLE path.
        #   2) a LiveKit data message {"type":"approved"|"rejected"} from the web —
        #      faster but best-effort (cross-process data packets can be dropped).
        def _announce_decision(status: str) -> None:
            if decided[0]:
                return
            if status == "confirmed":
                sink("approved", None, "保安已放行，AI 通知访客", None)
                line = "好的，已经为您放行，请进，栏杆已经抬起，祝您一路顺利！"
            elif status == "rejected":
                sink("rejected", None, "保安拒绝放行，AI 告知访客", None)
                line = ("不好意思，门卫这边暂时无法为您放行，"
                        "麻烦您与接待人联系核实，或稍后再试，谢谢理解。")
            else:
                return
            decided[0] = True
            last_user[0] = time.monotonic()  # restart silence countdown so it isn't cut off
            logger.info("announce guard decision: %s", status)

            async def _go() -> None:
                try:
                    await _speak(session, cfg, line)
                except Exception:  # noqa: BLE001
                    logger.exception("decision announce error")

            asyncio.create_task(_go())

        @ctx.room.on("data_received")
        def _on_data(*args) -> None:  # noqa: ANN002 — sig varies by livekit version
            try:
                packet = args[0] if args else None
                raw = getattr(packet, "data", packet)
                msg = json.loads(bytes(raw).decode("utf-8"))
            except Exception:  # noqa: BLE001
                return
            mtype = msg.get("type")
            if mtype == "approved":
                _announce_decision("confirmed")
            elif mtype == "rejected":
                _announce_decision("rejected")

        # Phone keypad (DTMF) takeover: once the guard is in the call, 1=放行
        # (open gate + record released), 2=拒绝. Only the guard's keys count.
        @ctx.room.on("sip_dtmf_received")
        def _on_dtmf(*args) -> None:  # noqa: ANN002 — sig varies by livekit version
            try:
                ev = args[0] if args else None
                digit = getattr(ev, "digit", None) or getattr(ev, "code", None)
                participant = getattr(ev, "participant", None) or (
                    args[1] if len(args) > 1 else None)
                identity = getattr(participant, "identity", "") or ""
            except Exception:  # noqa: BLE001
                return
            if identity and not identity.startswith("guard"):
                return
            d = str(digit)
            from . import takeover

            def _announce_keypad(text: str) -> None:
                async def _go() -> None:
                    try:
                        await _speak(session, cfg, text)
                    except Exception:  # noqa: BLE001
                        logger.exception("keypad announce error")

                asyncio.create_task(_go())

            if d == "1":
                sink("confirmed", None, "门卫电话按键放行（1）", None)
                try:
                    takeover.release(reg.info.to_dict(),
                                     getattr(reg.notifier, "last_visit_id", None), cfg.timezone)
                except Exception:  # noqa: BLE001
                    logger.exception("dtmf release error")
                _announce_keypad("好的，已经为您放行，请进，栏杆已经抬起。")  # feedback
            elif d == "2":
                sink("escalation", None, "门卫电话按键拒绝放行（2）", None)
                try:
                    takeover.deny(reg.info.to_dict())
                except Exception:  # noqa: BLE001
                    logger.exception("dtmf deny error")
                _announce_keypad("好的，本次未能放行，已记录，麻烦您配合，谢谢。")  # feedback

        # Human takeover: a guard joining (identity 'guard*') makes the AI hand off.
        @ctx.room.on("participant_connected")
        def _on_participant(participant) -> None:  # noqa: ANN001
            identity = getattr(participant, "identity", "") or ""
            if not identity.startswith("guard"):
                _prefill_caller_phone(participant)  # SIP caller joined → prefill
                return
            sink("human_joined", None, f"保安已接入通话（{identity}）", None)
            # A human now owns the mic — stop the echo guard from auto-unmuting the
            # AI's ears after its DTMF-feedback lines (the takeover keeps them muted).
            ears_locked[0] = True
            is_phone_guard = identity == "guard-phone"
            # Neutral line — the VISITOR hears it too, so DON'T read keypad
            # instructions to the guard here (那些在卡片/介入页上已经写了).
            line = ("好的，已经帮您接通门卫，下面由门卫师傅为您处理。"
                    if is_phone_guard
                    else "门卫师傅来了，由他来跟您说，我先退下。")

            async def _handoff() -> None:
                try:
                    if is_phone_guard:
                        # Keep the AI in the room so it can VOICE the keypad result
                        # (按 1 放行 / 按 2 拒绝 → 给门卫反馈). Mute its ears so it
                        # won't interject while the guard and visitor talk.
                        try:
                            session.input.set_audio_enabled(False)
                        except Exception:  # noqa: BLE001
                            logger.exception("mute input failed")
                        await _speak(session, cfg, line, allow_interruptions=False)
                    else:
                        await _speak(session, cfg, line, allow_interruptions=False)
                        await session.aclose()  # browser guard talks + releases on dashboard
                except Exception:  # noqa: BLE001
                    logger.exception("handoff error")

            asyncio.create_task(_handoff())

    await session.start(agent=agent, room=ctx.room)

    # Agent speaks first — the 25-second clock starts here. realtime can't say() a
    # fixed string, so _speak() asks the model to voice it; pipeline say()s it.
    if is_guard:
        greeting = "门卫您好，您想查什么？比如今天放行了多少辆车、最近哪个时段最忙。"
    else:
        # Phone calls prefill the mobile from caller-ID → skip asking for it (省一问).
        # No number (caller-ID stripped, or browser/QR access) → fall back to asking.
        greeting = GREETING if (reg and reg.info.phone) else GREETING_ASK_PHONE
    # Fixed opener: read it word-for-word so every call greets identically.
    await _speak(session, cfg, greeting, allow_interruptions=True, verbatim=True)

    # Keep the line open while the visitor waits for the guard's decision — DON'T
    # hang up just because registration finished (user feedback: 让访客等放行的
    #时候先别挂，门卫出结果再挂). After the guard approves/rejects, the AI announces
    # it (sets decided[0]) and we hang up once the visitor falls silent again. A
    # global max_call_sec cap guards against a guard who never acts / a stuck line.
    if not is_guard and (cfg.hangup_silence_sec or cfg.max_call_sec):
        async def _idle_watchdog() -> None:
            t0 = time.monotonic()
            while True:
                await asyncio.sleep(1.0)
                now = time.monotonic()
                if cfg.max_call_sec and now - t0 > cfg.max_call_sec:
                    logger.info("max call duration reached → hang up")
                    break
                # Reliable guard-decision signal: poll the visit status the web side
                # flips on /confirm or /reject (shared DB). First to fire (this or the
                # LiveKit data message) announces via the idempotent _announce_decision.
                if not decided[0]:
                    vid = getattr(getattr(reg, "notifier", None), "last_visit_id", None)
                    if vid:
                        try:
                            from .db import repo as _repo

                            v = _repo.get_visit_by_id(vid)
                            if v is not None and v.status in ("confirmed", "rejected"):
                                _announce_decision(v.status)
                        except Exception:  # noqa: BLE001
                            logger.exception("decision poll error")
                if (cfg.hangup_silence_sec and decided[0]
                        and now - last_user[0] > cfg.hangup_silence_sec):
                    logger.info("post-decision silence → hang up")
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
