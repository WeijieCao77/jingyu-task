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
