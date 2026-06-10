"""Route the guard notification to the configured channel.

`NOTIFY_CHANNEL` picks one of discord (demo default) / telegram / wecom (China
production). All share the same card content; only the transport differs — so
the rest of the system (agent, dashboard, confirm flow) is channel-agnostic.
"""

from __future__ import annotations

from . import discord, telegram, wecom


async def push(settings, visit: dict, confirm_url: str) -> bool:
    channel = (settings.notify_channel or "discord").lower()
    if channel == "discord":
        return await discord.send(settings.discord_webhook_url, visit, confirm_url)
    if channel == "telegram":
        return await telegram.send(
            settings.telegram_bot_token, settings.telegram_chat_id, visit, confirm_url
        )
    if channel == "wecom":
        return await wecom.send_visitor_card(settings.wecom_webhook_url, visit, confirm_url)
    # Unknown channel → don't fail the call; surface the card on stdout.
    print(f"[NOTIFY] 未知渠道 {channel}，卡片内容：", visit, confirm_url)
    return False
