"""Text simulator for the visitor-registration conversation.

Usage:
  python -m visitor_agent.sim.run_text                       # interactive
  python -m visitor_agent.sim.run_text --scenario FILE.json  # scripted turns
  python -m visitor_agent.sim.run_text --live                # use LiveNotifier (real DB/WeCom)

The agent uses the same SYSTEM_PROMPT + tools as the phone agent; only the
transport differs (typed text vs streamed audio). Great for iterating on the
"like a real guard" dialogue without spending phone minutes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time

from ..config import get_settings
from ..prompts import SYSTEM_PROMPT
from ..session_logic import LiveNotifier, MockNotifier, RegistrationSession

TOOLS = [
    {
        "name": "record_visitor_info",
        "description": "记录访客信息（可增量、可多次调用）。听到任何一项就立刻调用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "plate": {"type": "string", "description": "车牌号，如 沪A12345"},
                "company": {"type": "string", "description": "来访单位 / 找的公司"},
                "reason": {"type": "string", "description": "来访事由，如 送货"},
                "phone": {"type": "string", "description": "手机号"},
                "name": {"type": "string", "description": "访客称呼/姓名（如张师傅，提到才填）"},
            },
        },
    },
    {
        "name": "complete_registration",
        "description": "四项信息齐全后调用：完成登记并推送门卫。",
        "input_schema": {"type": "object", "properties": {}},
    },
]


async def _dispatch(reg: RegistrationSession, name: str, args: dict) -> str:
    if name == "record_visitor_info":
        return reg.record(**args)
    if name == "complete_registration":
        return await reg.complete()
    return f"unknown tool {name}"


async def run(scenario: list[str] | None, live: bool) -> None:
    import anthropic

    cfg = get_settings()
    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key or None)

    notifier = LiveNotifier(cfg) if live else MockNotifier()
    lookup = None
    event_sink = None
    call_id = "sim"
    if live:
        import json as _json
        import time as _time

        from ..db import repo
        from ..session_logic import make_db_lookup

        repo.init_db(cfg.database_url)
        lookup = make_db_lookup()
        call_id = f"sim-{int(_time.time())}"

        def event_sink(kind, role, text, payload):  # noqa: ANN001
            repo.log_event(
                call_id, kind, role=role, text=text,
                payload=_json.dumps(payload, ensure_ascii=False) if payload else None,
            )

        event_sink("call_started", None, f"文本仿真来电（{call_id}）", None)

    reg = RegistrationSession(
        notifier=notifier, lookup_returning=lookup, tz=cfg.timezone, event_sink=event_sink
    )
    messages: list[dict] = []

    print("=== 门卫语音 Agent · 文本仿真 ===")
    print(f"AGENT> {SYSTEM_PROMPT and ''}您好，请问车牌号多少，今天找哪家公司，什么事儿？\n")

    turns = iter(scenario) if scenario else None
    t0 = time.monotonic()
    while True:
        if turns is not None:
            try:
                user = next(turns)
            except StopIteration:
                break
            print(f"USER > {user}")
        else:
            try:
                user = input("USER > ").strip()
            except EOFError:
                break
            if user in {"exit", "quit", ""}:
                break

        messages.append({"role": "user", "content": user})
        if event_sink:
            event_sink("user", "user", user, None)

        # Inner tool-use loop for this user turn.
        for _ in range(6):
            resp = client.messages.create(
                model=cfg.llm_model,
                max_tokens=512,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )
            text = "".join(b.text for b in resp.content if b.type == "text").strip()
            if text:
                print(f"AGENT> {text}")
                if event_sink:
                    event_sink("agent", "assistant", text, None)
            if resp.stop_reason != "tool_use":
                break
            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for block in resp.content:
                if block.type == "tool_use":
                    out = await _dispatch(reg, block.name, block.input or {})
                    print(f"   · [{block.name}] {out}")
                    results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": out}
                    )
            messages.append({"role": "user", "content": results})

        if reg.completed:
            print(f"\n✅ 登记完成，用时 {time.monotonic() - t0:.1f}s（仅供参考，非真实电话延迟）")
            break


def main() -> None:
    parser = argparse.ArgumentParser(description="Visitor agent text simulator")
    parser.add_argument("--scenario", help="JSON file: a list of user utterances")
    parser.add_argument("--live", action="store_true", help="use real DB + WeCom push")
    ns = parser.parse_args()

    scenario = None
    if ns.scenario:
        with open(ns.scenario, encoding="utf-8") as f:
            scenario = json.load(f)

    asyncio.run(run(scenario, ns.live))


if __name__ == "__main__":
    main()
