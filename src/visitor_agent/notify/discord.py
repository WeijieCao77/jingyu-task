"""Discord webhook notifier — the default demo channel (US-friendly, 1 URL).

Create a webhook in any Discord channel (Channel Settings → Integrations →
Webhooks → New Webhook → Copy URL) and put it in DISCORD_WEBHOOK_URL. The card
is sent as an embed with a clickable "确认放行" link.
"""

from __future__ import annotations

import logging

import httpx

from .common import is_returning, title, visitor_rows

logger = logging.getLogger("visitor_agent.discord")


def build_payload(visit: dict, confirm_url: str) -> dict:
    desc = "\n".join(f"**{k}**：{v}" for k, v in visitor_rows(visit))
    desc += f"\n\n[✅ 确认放行]({confirm_url})"
    return {
        "embeds": [
            {
                "title": title(visit),
                "description": desc,
                "color": 0xC9742E if not is_returning(visit) else 0x39B54A,
            }
        ]
    }


async def send(webhook_url: str, visit: dict, confirm_url: str, timeout: float = 5.0) -> bool:
    if not webhook_url:
        logger.warning("DISCORD_WEBHOOK_URL not set; printing instead")
        print("[DISCORD] (未配置 webhook) 将要推送：", build_payload(visit, confirm_url))
        return False
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(webhook_url, json=build_payload(visit, confirm_url))
        # Discord returns 204 No Content on success.
        return resp.status_code in (200, 204)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Discord push error: %s", exc)
        return False
