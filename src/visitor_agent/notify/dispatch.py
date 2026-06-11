"""Route the guard notification to one or more channels.

`NOTIFY_CHANNEL` is a comma-separated list, so Telegram and WeCom can run in
parallel (`NOTIFY_CHANNEL=telegram,wecom`). All channels share the same card
content; only the transport differs — the rest of the system (agent, dashboard,
confirm flow) is channel-agnostic. `none` = no external push (guard acts on the
dashboard).
"""

from __future__ import annotations

from . import discord, telegram, wecom


async def _send_one(settings, channel: str, visit: dict, confirm_url: str) -> bool:
    if channel == "discord":
        return await discord.send(settings.discord_webhook_url, visit, confirm_url)
    if channel == "telegram":
        return await telegram.send(
            settings.telegram_bot_token, settings.telegram_chat_id, visit, confirm_url
        )
    if channel == "wecom":
        return await wecom.send_visitor_card(settings.wecom_webhook_url, visit, confirm_url)
    print(f"[NOTIFY] 未知渠道 {channel}，卡片内容：", visit, confirm_url)
    return False


async def push(settings, visit: dict, confirm_url: str) -> bool:
    """Push to every configured channel; True if any succeeded (or none needed)."""
    raw = (settings.notify_channel or "none").lower()
    channels = [c.strip() for c in raw.split(",") if c.strip()]
    # Drop the no-op channels; if nothing real is left, the dashboard is the channel.
    external = [c for c in channels if c not in ("none", "dashboard", "console")]
    if not external:
        return True
    results = [await _send_one(settings, c, visit, confirm_url) for c in external]
    return any(results)
