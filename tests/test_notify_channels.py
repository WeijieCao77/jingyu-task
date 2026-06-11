from visitor_agent.notify import discord, telegram


def _visit():
    return {
        "plate": "沪A12345",
        "company": "蓝色鲸鱼科技",
        "reason": "送货",
        "phone": "13800138000",
        "entry_time": "2025-04-13 14:30",
    }


def test_discord_embed_has_fields_and_link():
    p = discord.build_payload(_visit(), "https://x.test/confirm?token=abc")
    desc = p["embeds"][0]["description"]
    for v in _visit().values():
        assert v in desc
    assert "[✅ 确认放行](https://x.test/confirm?token=abc)" in desc


def test_discord_returning_color():
    v = _visit()
    v["returning"] = True
    p = discord.build_payload(v, "https://x/c?token=t")
    assert "回访车辆" in p["embeds"][0]["title"]


def test_telegram_has_button_and_fields():
    p = telegram.build_payload(_visit(), "https://x.test/confirm?token=abc", "12345")
    assert p["chat_id"] == "12345"
    assert p["reply_markup"]["inline_keyboard"][0][0]["url"] == "https://x.test/confirm?token=abc"
    for v in _visit().values():
        assert v in p["text"]


def test_dispatch_multi_channel(monkeypatch):
    import asyncio
    import types

    from visitor_agent.notify import dispatch

    called = []

    async def fake_discord(url, visit, confirm_url):
        called.append("discord"); return True

    async def fake_telegram(token, chat, visit, confirm_url):
        called.append("telegram"); return True

    monkeypatch.setattr(dispatch.discord, "send", fake_discord)
    monkeypatch.setattr(dispatch.telegram, "send", fake_telegram)

    settings = types.SimpleNamespace(
        notify_channel="telegram, wecom, discord",  # spaces + order mixed
        discord_webhook_url="x", telegram_bot_token="t", telegram_chat_id="c",
        wecom_webhook_url="",  # wecom unconfigured -> prints, returns False
    )
    ok = asyncio.run(dispatch.push(settings, {"plate": "沪A1"}, "https://x/c?token=t"))
    assert ok is True               # at least one channel succeeded
    assert "telegram" in called and "discord" in called


def test_dispatch_none(monkeypatch):
    import asyncio
    import types

    from visitor_agent.notify import dispatch

    s = types.SimpleNamespace(notify_channel="none")
    assert asyncio.run(dispatch.push(s, {"plate": "沪A1"}, "u")) is True


def test_name_included_when_present():
    from visitor_agent.notify.wecom import build_markdown

    v = dict(_visit(), name="张师傅")
    assert "张师傅" in discord.build_payload(v, "https://x/c?token=t")["embeds"][0]["description"]
    assert "张师傅" in telegram.build_payload(v, "https://x/c?token=t", "1")["text"]
    assert "张师傅" in build_markdown(v, "https://x/c?token=t")
