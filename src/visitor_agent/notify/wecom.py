"""Push a structured visitor card to the guard's WeCom (企业微信) group bot.

The group-bot webhook is a one-directional push, so the "guard confirms and the
gate opens" step is modelled as a tokenized link inside the markdown card: the
guard taps it in the WeCom in-app browser, the link hits our /confirm endpoint,
and that endpoint fires the gate stub. Pure formatting (`build_markdown`) is kept
separate from the network call so it can be unit-tested offline.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger("visitor_agent.wecom")


def build_markdown(visit: dict, confirm_url: str) -> str:
    """Render the visitor card as WeCom markdown with a tap-to-approve link."""
    plate = visit.get("plate") or "—"
    company = visit.get("company") or "—"
    reason = visit.get("reason") or "—"
    phone = visit.get("phone") or "—"
    entry_time = visit.get("entry_time") or "—"
    returning = "（回访车辆）" if visit.get("returning") else ""
    name_line = f"> **姓名**：{visit['name']}\n" if visit.get("name") else ""

    return (
        f"## 🚗 访客登记 {returning}\n"
        f"> **车牌号**：<font color=\"info\">{plate}</font>\n"
        f"> **来访单位**：{company}\n"
        f"> **来访事由**：{reason}\n"
        f"> **手机号**：{phone}\n"
        f"{name_line}"
        f"> **入场时间**：{entry_time}\n\n"
        f"[✅ 确认放行]({confirm_url})"
    )


def build_payload(visit: dict, confirm_url: str) -> dict:
    return {"msgtype": "markdown", "markdown": {"content": build_markdown(visit, confirm_url)}}


async def send_visitor_card(webhook_url: str, visit: dict, confirm_url: str,
                            timeout: float = 5.0) -> bool:
    """POST the card to the WeCom webhook. Returns True on WeCom errcode==0."""
    if not webhook_url:
        logger.warning("WECOM_WEBHOOK_URL not set; skipping push")
        print("[WECOM] (未配置 webhook) 将要推送：\n" + build_markdown(visit, confirm_url))
        return False
    payload = build_payload(visit, confirm_url)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(webhook_url, json=payload)
            data = resp.json()
        ok = data.get("errcode") == 0
        if not ok:
            logger.error("WeCom push failed: %s", data)
        return ok
    except Exception as exc:  # noqa: BLE001 — demo: log and report failure
        logger.exception("WeCom push error: %s", exc)
        return False
