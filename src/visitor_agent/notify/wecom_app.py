"""Push a visitor card via a WeCom (企业微信) **self-built app** API.

Unlike the group-bot webhook (`wecom.py`), this needs no group — it messages the
app's members directly (touser="@all"), so it works even for a one-person org.
Setup (企业微信 管理后台 work.weixin.qq.com):
  - 我的企业 → 企业信息 → **企业ID** = WECOM_CORP_ID
  - 应用管理 → 自建 → 创建应用（可见范围含你本人）→ **AgentId** = WECOM_AGENT_ID
                                                  → **Secret** = WECOM_APP_SECRET
The "确认放行" step is a tokenized link inside a textcard: the guard taps the card
in the 企业微信 in-app browser → hits /confirm → fires the gate. Same shape as the
Telegram/WeCom-webhook cards (formatting reuses notify.common).
"""

from __future__ import annotations

import logging
import time

import httpx

from .common import status_lines, title, visitor_rows

logger = logging.getLogger("visitor_agent.wecom_app")

_BASE = "https://qyapi.weixin.qq.com/cgi-bin"
# Cache the access_token per corpid (valid ~7200s); refresh a bit early.
_token_cache: dict[str, tuple[str, float]] = {}


def build_textcard(visit: dict, confirm_url: str) -> dict:
    """A 企业微信 textcard: whole card is tappable (→ confirm_url)."""
    desc_lines = list(status_lines(visit)) + [f"{k}：{v}" for k, v in visitor_rows(visit)]
    return {
        "title": title(visit),
        "description": "\n".join(desc_lines),
        "url": confirm_url,
        "btntxt": "放行",
    }


def build_payload(visit: dict, confirm_url: str, agent_id: str) -> dict:
    return {
        "touser": "@all",
        "msgtype": "textcard",
        "agentid": int(agent_id) if str(agent_id).isdigit() else agent_id,
        "textcard": build_textcard(visit, confirm_url),
    }


async def _get_token(corp_id: str, secret: str, timeout: float = 5.0) -> str | None:
    cached = _token_cache.get(corp_id)
    if cached and time.time() < cached[1]:
        return cached[0]
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                f"{_BASE}/gettoken", params={"corpid": corp_id, "corpsecret": secret}
            )
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.exception("WeCom-app gettoken error: %s", exc)
        return None
    if data.get("errcode") == 0 and data.get("access_token"):
        token = data["access_token"]
        _token_cache[corp_id] = (token, time.time() + int(data.get("expires_in", 7200)) - 300)
        return token
    logger.error("WeCom-app gettoken failed: %s", data)
    return None


async def _post_message(corp_id: str, secret: str, payload: dict, timeout: float = 5.0) -> bool:
    token = await _get_token(corp_id, secret, timeout)
    if not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{_BASE}/message/send", params={"access_token": token}, json=payload
            )
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.exception("WeCom-app send error: %s", exc)
        return False
    ok = data.get("errcode") == 0
    if not ok:
        logger.error("WeCom-app push failed: %s", data)
    return ok


async def send_visitor_card(corp_id: str, secret: str, agent_id: str, visit: dict,
                            confirm_url: str, timeout: float = 5.0) -> bool:
    """Send the visitor card (textcard) to the app's members. True on errcode==0."""
    if not (corp_id and secret and agent_id):
        logger.warning("WECOM_CORP_ID/AGENT_ID/APP_SECRET not set; skipping push")
        print("[WECOM_APP] (未配置) 将要推送：", title(visit), confirm_url)
        return False
    return await _post_message(corp_id, secret, build_payload(visit, confirm_url, agent_id), timeout)


async def send_text(corp_id: str, secret: str, agent_id: str, text: str,
                    timeout: float = 5.0) -> bool:
    """Plain markdown push for transfer-to-human alerts."""
    if not (corp_id and secret and agent_id):
        print("[WECOM_APP] (未配置) " + text)
        return False
    payload = {
        "touser": "@all",
        "msgtype": "markdown",
        "agentid": int(agent_id) if str(agent_id).isdigit() else agent_id,
        "markdown": {"content": text},
    }
    return await _post_message(corp_id, secret, payload, timeout)
