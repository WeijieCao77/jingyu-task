"""Telegram bot notifier — US-friendly demo channel with a tap-to-confirm button.

Setup: talk to @BotFather → /newbot → get TELEGRAM_BOT_TOKEN. Send your bot a
message, then GET https://api.telegram.org/bot<token>/getUpdates to find your
chat id → TELEGRAM_CHAT_ID. The "确认放行" button is a Telegram inline URL button.
"""

from __future__ import annotations

import html
import logging
from urllib.parse import urlparse

import httpx

from .common import status_lines, title, visitor_rows

logger = logging.getLogger("visitor_agent.telegram")


def button_safe_url(url: str | None) -> bool:
    """Telegram rejects inline-button URLs pointing at localhost (and one bad
    button fails the WHOLE message). A public/tunnel/LAN host is fine. So we
    only put the confirm link in a button when the host is reachable; otherwise
    it goes into the message body as plain text."""
    try:
        host = (urlparse(url or "").hostname or "").lower()
    except Exception:  # noqa: BLE001
        return False
    return host not in ("", "localhost", "127.0.0.1", "0.0.0.0", "::1")


def build_text(visit: dict, confirm_url: str | None = None) -> str:
    lines = [f"<b>{html.escape(title(visit))}</b>"]
    lines += [html.escape(s) for s in status_lines(visit)]
    lines += [f"{k}：{html.escape(str(v))}" for k, v in visitor_rows(visit)]
    # When the link can't be a button (localhost), surface it in the body so the
    # guard still has a tappable confirm link.
    if confirm_url and not button_safe_url(confirm_url):
        lines.append(f"\n👉 确认放行：{confirm_url}")
    return "\n".join(lines)


def build_payload(visit: dict, confirm_url: str, chat_id: str) -> dict:
    payload = {
        "chat_id": chat_id,
        "text": build_text(visit, confirm_url),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if button_safe_url(confirm_url):
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": "✅ 确认放行", "url": confirm_url}]]
        }
    return payload


async def send(bot_token: str, chat_id: str, visit: dict, confirm_url: str,
               timeout: float = 5.0) -> bool:
    if not (bot_token and chat_id):
        logger.warning("TELEGRAM_BOT_TOKEN/CHAT_ID not set; printing instead")
        print("[TELEGRAM] (未配置) 将要推送：\n" + build_text(visit, confirm_url))
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = build_payload(visit, confirm_url, chat_id)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            if data.get("ok"):
                return True
            # An invalid button URL fails the entire sendMessage. Degrade once to
            # a plain-text card (link in the body) so the message at least lands.
            desc = str(data.get("description", "")).upper()
            if "reply_markup" in payload and "URL" in desc:
                logger.warning("Telegram rejected button URL; retrying as text: %s", desc)
                fallback = {
                    "chat_id": chat_id,
                    "text": build_text(visit) + f"\n👉 确认放行：{confirm_url}",
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                }
                resp = await client.post(url, json=fallback)
                return bool(resp.json().get("ok"))
            logger.error("Telegram push failed: %s", data)
            return False
    except Exception as exc:  # noqa: BLE001
        logger.exception("Telegram push error: %s", exc)
        return False
