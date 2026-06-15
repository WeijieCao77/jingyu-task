"""Bonus: a natural-language guard query agent over the visit records.

The guard can ask things like "本周一共多少访问车辆？" / "什么时间段访问最多？" /
"沪A12345 这个月来了几次？". Rather than free-form text-to-SQL (injection-prone),
the agent is given a few safe, parameterized tools; Claude picks the tool and
arguments, we run the read-only query, and Claude phrases the answer.

CLI:  python -m visitor_agent.guard_query "本周一共多少访问车辆？"
API:  POST /guard/query  {"question": "..."}
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from .config import get_settings
from .db import repo

TOOLS = [
    {
        "name": "count_visits",
        "description": "统计访问车辆数量，可按时间范围、来访单位、放行状态过滤。返回整数。"
                       "时间范围**优先用 range**（today/week/month/all），不要自己算日期，"
                       "这样和后台数字一致；只有要精确自定义区间才用 since_iso/until_iso。"
                       "问'多少辆被放行/已放行'时 status 传 confirmed；'待核对/未放行'传 pending。",
        "input_schema": {
            "type": "object",
            "properties": {
                "range": {"type": "string", "description": "时间范围：today=今天 / week=本周 / month=本月 / all=全部（优先用这个）"},
                "since_iso": {"type": "string", "description": "自定义起始时间 ISO8601（含），可空"},
                "until_iso": {"type": "string", "description": "自定义结束时间 ISO8601（含），可空"},
                "company": {"type": "string", "description": "来访单位关键词，可空"},
                "status": {"type": "string", "description": "放行状态：confirmed=已放行 / pending=待核对；留空=全部"},
            },
        },
    },
    {
        "name": "list_visits",
        "description": "按车牌/手机号/单位列出访问记录（最近优先）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "plate": {"type": "string"},
                "phone": {"type": "string"},
                "company": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "busiest_hours",
        "description": "返回各小时(0-23)的访问次数直方图，用于判断高峰时段。时间范围优先用 range。",
        "input_schema": {
            "type": "object",
            "properties": {
                "range": {"type": "string", "description": "today/week/month/all，优先用这个"},
                "since_iso": {"type": "string", "description": "自定义起始时间 ISO8601，可空"},
            },
        },
    },
    {
        "name": "frequent_visitors",
        "description": "返回常客名单/访客画像（按人聚合）：来访次数、车牌、常去单位、姓名、最近一次。",
        "input_schema": {
            "type": "object",
            "properties": {
                "min_visits": {"type": "integer", "description": "至少来访几次才算常客，默认1"},
                "limit": {"type": "integer", "description": "最多返回几条，默认20"},
            },
        },
    },
]


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _resolve_window(args: dict):
    """(since, until) for a tool call. Prefer the `range` enum (today/week/month/
    all) — resolved by the SAME helper the structured /api/query uses — so NL
    answers match the dashboard exactly. Fall back to custom since_iso/until_iso."""
    rng = (args.get("range") or "").strip().lower()
    if rng in ("today", "week", "month", "all"):
        from .timeutil import range_window

        return range_window(rng, get_settings().timezone)
    return _parse_iso(args.get("since_iso")), _parse_iso(args.get("until_iso"))


def run_tool(name: str, args: dict) -> str:
    """Execute one read-only query tool and return a JSON string result."""
    if name == "count_visits":
        since, until = _resolve_window(args)
        n = repo.count_visits(
            since=since,
            until=until,
            company=args.get("company"),
            status=args.get("status") or None,
        )
        return json.dumps({"count": n})
    if name == "list_visits":
        visits = repo.visits_for(
            plate=args.get("plate"),
            phone=args.get("phone"),
            company=args.get("company"),
            limit=int(args.get("limit") or 20),
        )
        return json.dumps([v.to_dict() for v in visits], ensure_ascii=False)
    if name == "busiest_hours":
        since, _ = _resolve_window(args)
        hist = repo.visits_by_hour(since=since)
        return json.dumps({"by_hour": hist})
    if name == "frequent_visitors":
        profiles = repo.visitor_profiles(
            limit=int(args.get("limit") or 20),
            min_visits=int(args.get("min_visits") or 1),
        )
        return json.dumps(profiles, ensure_ascii=False)
    return json.dumps({"error": f"unknown tool {name}"})


def _system_prompt(cfg) -> str:
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo(cfg.timezone))
    return (
        "你是工业园区的门卫数据助手，和保安多轮对话。基于访客登记数据库回答中文提问。"
        f"当前时间是 {now.isoformat()}（{cfg.timezone}）。"
        "**今天/本周/本月/全部 这类范围，直接给工具传 range 参数（today/week/month/all），"
        "不要自己算 ISO 日期**——这样数字才和后台一致；只有要精确自定义区间时才用 since_iso/until_iso。"
        "支持追问：结合上文理解'那上个月呢''他呢'这类省略问法。"
        "**回答前必须先调用查询工具拿到真实数据，严禁凭空报数字或拒答**；"
        "只有工具确实返回空/0 时才说没有。问放行数量时记得用 status=confirmed。"
        "用简短中文口语回答，给出具体数字。"
    )


def _clean_history(history: list[dict] | None, max_turns: int = 12) -> list[dict]:
    """Keep only well-formed user/assistant text turns (for multi-turn context)."""
    out: list[dict] = []
    for m in (history or [])[-max_turns:]:
        role, content = m.get("role"), m.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            out.append({"role": role, "content": content.strip()})
    return out


def _answer_openai(question: str, model: str, max_steps: int,
                   history: list[dict] | None = None) -> str:
    import json as _json

    import openai

    cfg = get_settings()
    client = openai.OpenAI(api_key=cfg.openai_api_key or None)
    tools = [
        {"type": "function", "function": {
            "name": t["name"], "description": t["description"], "parameters": t["input_schema"]
        }} for t in TOOLS
    ]
    messages = [{"role": "system", "content": _system_prompt(cfg)}]
    messages += _clean_history(history)
    messages.append({"role": "user", "content": question})
    for i in range(max_steps):
        kwargs = {"model": model, "messages": messages, "tools": tools}
        if i == 0:
            kwargs["tool_choice"] = "required"  # must query the DB, never guess/refuse
        resp = client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return (msg.content or "").strip()
        # Re-append the assistant turn as a clean dict (passing the raw SDK
        # object back can carry null fields the API rejects).
        assistant = {"role": "assistant", "content": msg.content}
        assistant["tool_calls"] = [
            {
                "id": c.id,
                "type": "function",
                "function": {"name": c.function.name, "arguments": c.function.arguments},
            }
            for c in msg.tool_calls
        ]
        messages.append(assistant)
        for call in msg.tool_calls:
            out = run_tool(call.function.name, _json.loads(call.function.arguments or "{}"))
            messages.append({"role": "tool", "tool_call_id": call.id, "content": out})
    return "（查询步数超限，请把问题问得更具体一些。）"


def _answer_anthropic(question: str, model: str, max_steps: int,
                      history: list[dict] | None = None) -> str:
    import anthropic

    cfg = get_settings()
    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key or None)
    messages: list[dict] = _clean_history(history) + [{"role": "user", "content": question}]
    for i in range(max_steps):
        kwargs = dict(model=model, max_tokens=1024, system=_system_prompt(cfg),
                      tools=TOOLS, messages=messages)
        if i == 0:
            kwargs["tool_choice"] = {"type": "any"}  # must query the DB first
        resp = client.messages.create(**kwargs)
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text").strip()
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type == "tool_use":
                out = run_tool(block.name, block.input or {})
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
        messages.append({"role": "user", "content": results})
    return "（查询步数超限，请把问题问得更具体一些。）"


def answer_question(question: str, history: list[dict] | None = None,
                    model: str | None = None, max_steps: int = 5) -> str:
    """Answer a guard's NL question (with optional prior turns for follow-ups);
    uses whichever LLM provider is configured."""
    cfg = get_settings()
    repo.init_db(cfg.database_url)
    # Model tiering: the query agent can run a different (cheaper/stronger) model
    # than the conversational brain — GUARD_QUERY_MODEL, else fall back to LLM_MODEL.
    model = model or cfg.guard_query_model or cfg.llm_model
    if cfg.llm_provider == "anthropic":
        return _answer_anthropic(question, model, max_steps, history)
    return _answer_openai(question, model, max_steps, history)


def main() -> None:
    import sys

    question = " ".join(sys.argv[1:]) or "本周一共多少访问车辆？"
    print(answer_question(question))


if __name__ == "__main__":
    main()
