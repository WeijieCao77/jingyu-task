"""Telegram bot notifier — US-friendly demo channel with a tap-to-confirm button.

Setup: talk to @BotFather → /newbot → get TELEGRAM_BOT_TOKEN. Send your bot a
message, then GET https://api.telegram.org/bot<token>/getUpdates to find your
chat id → TELEGRAM_CHAT_ID. The "确认放行" button is a Telegram inline URL button.
"""

from __future__ import annotations

import html
import logging

import httpx

from .common import title, visitor_rows

logger = logging.getLogger("visitor_agent.telegram")


def build_text(visit: dict) -> str:
    lines = [f"<b>{title(visit)}</b>"]
    lines += [f"{k}：{html.escape(str(v))}" for k, v in visitor_rows(visit)]
    return "\n".join(lines)


def build_payload(visit: dict, confirm_url: str, chat_id: str) -> dict:
    return {
        "chat_id": chat_id,
        "text": build_text(visit),
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [[{"text": "✅ 确认放行", "url": confirm_url}]]
        },
    }


async def send(bot_token: str, chat_id: str, visit: dict, confirm_url: str,
               timeout: float = 5.0) -> bool:
    if not (bot_token and chat_id):
        logger.warning("TELEGRAM_BOT_TOKEN/CHAT_ID not set; printing instead")
        print("[TELEGRAM] (未配置) 将要推送：\n" + build_text(visit) + f"\n确认：{confirm_url}")
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=build_payload(visit, confirm_url, chat_id))
        return bool(resp.json().get("ok"))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Telegram push error: %s", exc)
        return False
