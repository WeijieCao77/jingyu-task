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


def test_push_alert_routes_text(monkeypatch):
    import asyncio
    import types

    from visitor_agent.notify import dispatch

    seen = []

    async def fake_tg(token, chat, text):
        seen.append(("telegram", text)); return True

    monkeypatch.setattr(dispatch.telegram, "send_text", fake_tg)
    s = types.SimpleNamespace(notify_channel="telegram", telegram_bot_token="t",
                              telegram_chat_id="c")
    ok = asyncio.run(dispatch.push_alert(s, "⚠️ 转人工 房间 voice-demo"))
    assert ok is True and seen and "转人工" in seen[0][1]
    # none → no-op success
    assert asyncio.run(dispatch.push_alert(types.SimpleNamespace(notify_channel="none"), "x")) is True


def test_name_included_when_present():
    from visitor_agent.notify.wecom import build_markdown

    v = dict(_visit(), name="张师傅")
    assert "张师傅" in discord.build_payload(v, "https://x/c?token=t")["embeds"][0]["description"]
    assert "张师傅" in telegram.build_payload(v, "https://x/c?token=t", "1")["text"]
    assert "张师傅" in build_markdown(v, "https://x/c?token=t")


# ----- returning + access flags surface on every channel -----

def test_returning_summary_on_cards():
    from visitor_agent.notify.wecom import build_markdown

    v = dict(_visit(), returning=True, returning_summary="张师傅 · 手机匹配·本人 · 第3次 · 上次蓝色鲸鱼／送货")
    assert "第3次" in telegram.build_text(v)
    assert "第3次" in discord.build_payload(v, "https://x/c?token=t")["embeds"][0]["description"]
    assert "第3次" in build_markdown(v, "https://x/c?token=t")


def test_blacklist_flag_on_cards():
    from visitor_agent.notify.common import title
    from visitor_agent.notify.wecom import build_markdown

    v = dict(_visit(), access_status="blacklist", access_summary="⛔ 黑名单 · 欠费 · 按车牌匹配")
    assert "黑名单" in title(v)
    assert "黑名单" in telegram.build_text(v)
    assert "黑名单" in build_markdown(v, "https://x/c?token=t")
    assert discord.build_payload(v, "https://x/c?token=t")["embeds"][0]["color"] == 0xD9352B


def test_whitelist_flag_on_cards():
    v = dict(_visit(), access_status="whitelist", access_summary="✅ 白名单 · 王总 · VIP · 按车牌匹配")
    assert "白名单" in telegram.build_payload(v, "https://x/c?token=t", "1")["text"]
    assert "白名单" in discord.build_payload(v, "https://x/c?token=t")["embeds"][0]["title"]


# ----- Telegram localhost button degradation (①) -----

def test_telegram_localhost_url_drops_button_keeps_link():
    p = telegram.build_payload(_visit(), "http://localhost:8080/confirm?token=t", "1")
    assert "reply_markup" not in p              # localhost button would fail the whole send
    assert "localhost:8080/confirm?token=t" in p["text"]  # link still reachable in body


def test_telegram_public_url_has_button():
    p = telegram.build_payload(_visit(), "http://100.67.103.51:8080/confirm?token=t", "1")
    assert p["reply_markup"]["inline_keyboard"][0][0]["url"].startswith("http://100.67.103.51")


def test_button_safe_url():
    assert telegram.button_safe_url("https://x.test/c") is True
    assert telegram.button_safe_url("http://100.67.103.51:8080/c") is True
    assert telegram.button_safe_url("http://localhost:8080/c") is False
    assert telegram.button_safe_url("http://127.0.0.1/c") is False
    assert telegram.button_safe_url("") is False
