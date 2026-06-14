"""Push a visitor card to the guard's **personal WeChat** via PushPlus.

PushPlus (https://www.pushplus.plus) relays to personal 微信 through a service
account — no enterprise, no group, no IP whitelist, works from any host. Simpler
format than a rich card (title + body + a tap-to-confirm link), but the 放行 link
still opens /confirm in WeChat's in-app browser and fires the gate.

Setup: 微信 关注 "pushplus 推送加" 公众号 (or pushplus.plus 扫码登录) → copy your
**token** → PUSHPLUS_TOKEN. Formatting reuses notify.common for parity.
"""

from __future__ import annotations

import html
import logging

import httpx

from .common import status_lines, title, visitor_rows

logger = logging.getLogger("visitor_agent.pushplus")

_URL = "https://www.pushplus.plus/send"


def build_content(visit: dict, confirm_url: str) -> str:
    """HTML body for the personal-WeChat message + a tap-to-confirm link."""
    lines = list(status_lines(visit)) + [f"{k}：{v}" for k, v in visitor_rows(visit)]
    body = "<br>".join(html.escape(s) for s in lines)
    return f"{body}<br><br><a href=\"{html.escape(confirm_url)}\">✅ 确认放行</a>"


def build_payload(token: str, visit: dict, confirm_url: str) -> dict:
    return {
        "token": token,
        "title": title(visit),
        "content": build_content(visit, confirm_url),
        "template": "html",
    }


async def _post(payload: dict, timeout: float = 5.0) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(_URL, json=payload)
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.exception("PushPlus error: %s", exc)
        return False
    ok = data.get("code") == 200
    if not ok:
        logger.error("PushPlus push failed: %s", data)
    return ok


async def send_visitor_card(token: str, visit: dict, confirm_url: str,
                            timeout: float = 5.0) -> bool:
    if not token:
        logger.warning("PUSHPLUS_TOKEN not set; skipping push")
        print("[PUSHPLUS] (未配置) 将要推送：", title(visit), confirm_url)
        return False
    return await _post(build_payload(token, visit, confirm_url), timeout)


async def send_text(token: str, text: str, timeout: float = 5.0) -> bool:
    """Plain-text alert (转人工 etc.) to personal WeChat."""
    if not token:
        print("[PUSHPLUS] (未配置) " + text)
        return False
    return await _post({"token": token, "title": "门卫告警", "content": text, "template": "txt"}, timeout)
