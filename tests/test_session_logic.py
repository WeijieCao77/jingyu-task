import asyncio

from visitor_agent.session_logic import MockNotifier, RegistrationSession


def test_record_then_complete_pushes_once():
    notifier = MockNotifier()
    reg = RegistrationSession(notifier=notifier)

    out = reg.record(plate="沪A12345", company="蓝色鲸鱼", reason="送货")
    assert "还缺" in out and "手机号" in out
    reg.record(phone="13800138000")
    assert reg.info.is_complete()

    result = asyncio.run(reg.complete())
    assert reg.completed
    assert len(notifier.calls) == 1
    pushed = notifier.calls[0]
    assert pushed["plate"] == "沪A12345"
    assert pushed["entry_time"]  # stamped
    assert "复述" in result or "登记完成" in result


def test_complete_blocks_when_incomplete():
    reg = RegistrationSession(notifier=MockNotifier())
    reg.record(plate="沪A12345")
    out = asyncio.run(reg.complete())
    assert "还差" in out
    assert not reg.completed


def test_returning_visitor_prefills_and_hints():
    def lookup(plate):
        return {"company": "蓝色鲸鱼", "reason": "送货"} if plate == "沪A12345" else None

    reg = RegistrationSession(notifier=MockNotifier(), lookup_returning=lookup)
    out = reg.record(plate="沪A12345")
    assert "回访车辆" in out
    # company/reason prefilled from history → only phone remains
    assert reg.info.missing_fields() == ["phone"]
