"""LiveKit Agents worker — the telephony entry point.

A Twilio phone number routes inbound calls (via SIP) into a LiveKit room; this
worker is dispatched per call, so each call gets its own RegistrationSession and
the design is naturally concurrent (multiple cars calling at once = multiple
independent jobs, no shared mutable state).

Run:  python -m visitor_agent.agent dev      # local dev (hot reload)
      python -m visitor_agent.agent start     # production worker
"""

from __future__ import annotations

import logging

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RunContext,
    WorkerOptions,
    cli,
    function_tool,
)

from .config import get_settings
from .db import repo
from .prompts import GREETING, SYSTEM_PROMPT
from .providers import build_llm, build_stt, build_tts, build_turn_detection, build_vad
from .session_logic import LiveNotifier, RegistrationSession, make_db_lookup

logger = logging.getLogger("visitor_agent.agent")


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
    ) -> str:
        """记录访客信息（可增量、可多次调用）。听到任何一项就立刻调用。

        Args:
            plate: 车牌号，如 沪A12345（原样传入即可）
            company: 来访单位 / 找的公司
            reason: 来访事由，如 送货、拜访、面试
            phone: 手机号（原样传入即可）
        """
        return self._reg.record(plate=plate, company=company, reason=reason, phone=phone)

    @function_tool()
    async def complete_registration(self, context: RunContext) -> str:  # noqa: ARG002
        """四项信息齐全后调用：完成登记、记录入场时间、推送门卫微信。"""
        return await self._reg.complete()


async def entrypoint(ctx: JobContext) -> None:
    cfg = get_settings()
    repo.init_db(cfg.database_url)

    await ctx.connect()

    reg = RegistrationSession(
        notifier=LiveNotifier(cfg),
        lookup_returning=make_db_lookup(),
        tz=cfg.timezone,
    )
    agent = VisitorAgent(reg)

    session = AgentSession(
        stt=build_stt(cfg),
        llm=build_llm(cfg),
        tts=build_tts(cfg),
        vad=build_vad(),
        turn_detection=build_turn_detection(),
    )

    await session.start(agent=agent, room=ctx.room)

    # Agent speaks first — this is when the 25-second clock starts.
    await session.say(GREETING, allow_interruptions=True)


def main() -> None:
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))


if __name__ == "__main__":
    main()
