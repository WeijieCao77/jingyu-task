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


def test_returning_visitor_by_plate_prefills_and_hints():
    def lookup(plate, phone):
        if plate == "沪A12345":
            return {"match_type": "plate", "visit_count": 2, "name": None,
                    "last_company": "蓝色鲸鱼", "last_reason": "送货", "last_time": None}
        return None

    reg = RegistrationSession(notifier=MockNotifier(), lookup_returning=lookup)
    out = reg.record(plate="沪A12345")
    assert "回访识别" in out and "可能换了司机" in out  # cautious phrasing for plate-only
    assert reg.info.missing_fields() == ["phone"]      # company/reason prefilled


def test_returning_visitor_by_phone_recognizes_person():
    def lookup(plate, phone):
        if phone == "13800138000":
            return {"match_type": "phone", "visit_count": 3, "name": "张师傅",
                    "last_company": "蓝色鲸鱼", "last_reason": "拜访", "last_time": None}
        return None

    reg = RegistrationSession(notifier=MockNotifier(), lookup_returning=lookup)
    # different car, but phone identifies the person
    out = reg.record(plate="浙B99999", phone="13800138000")
    assert "回访识别" in out and "张师傅" in out
    assert reg.info.company == "蓝色鲸鱼"
    assert reg.info.name == "张师傅"


def test_blacklist_flags_payload_and_emits_alert():
    events = []
    reg = RegistrationSession(
        notifier=MockNotifier(),
        access_check=lambda plate, phone: (
            {"status": "blacklist", "matched_on": "plate", "name": None, "reason": "欠费"}
            if plate == "沪A00000" else None
        ),
        event_sink=lambda kind, role, text, payload: events.append((kind, text)),
    )
    reg.record(plate="沪A00000", company="蓝色鲸鱼", reason="送货", phone="13800138000")
    assert any(k == "access_alert" for k, _ in events)  # guard alerted
    pushed = asyncio.run(_complete_and_capture(reg))
    assert pushed["access_status"] == "blacklist"
    assert "黑名单" in pushed["access_summary"]


def test_whitelist_flags_payload():
    reg = RegistrationSession(
        notifier=MockNotifier(),
        access_check=lambda plate, phone: (
            {"status": "whitelist", "matched_on": "phone", "name": "李经理", "reason": "VIP"}
            if phone == "13800138000" else None
        ),
    )
    reg.record(plate="沪A1", company="蓝色鲸鱼", reason="送货", phone="13800138000")
    pushed = asyncio.run(_complete_and_capture(reg))
    assert pushed["access_status"] == "whitelist"
    assert "常客" in pushed["access_summary"] and "李经理" in pushed["access_summary"]


def test_returning_summary_in_payload():
    reg = RegistrationSession(
        notifier=MockNotifier(),
        lookup_returning=lambda plate, phone: (
            {"match_type": "phone", "visit_count": 2, "name": "张师傅",
             "last_company": "蓝色鲸鱼", "last_reason": "送货", "last_time": None}
            if phone == "13800138000" else None
        ),
    )
    reg.record(plate="沪A1", company="蓝色鲸鱼", reason="送货", phone="13800138000")
    pushed = asyncio.run(_complete_and_capture(reg))
    assert pushed["returning"] is True
    assert "第3次" in pushed["returning_summary"] and "张师傅" in pushed["returning_summary"]


async def _complete_and_capture(reg) -> dict:
    await reg.complete()
    return reg.notifier.calls[-1]


def test_roster_miss_hints_to_escalate():
    # roster configured but company not found → hint nudges confirm-then-escalate
    reg = RegistrationSession(
        notifier=MockNotifier(),
        roster_match=lambda text: ("蓝色鲸鱼科技", 0.9) if "鲸鱼" in (text or "") else (None, 0.2),
    )
    out = reg.record(company="不存在的公司")
    assert "单位不在园区名单" in out and "转人工" in out


def test_invalid_phone_hints_reconfirm():
    reg = RegistrationSession(notifier=MockNotifier())
    out = reg.record(phone="1380013800")  # 10 digits
    assert "手机号位数异常" in out
    out2 = reg.record(phone="13800138000")  # valid 11 → no warning
    assert "手机号位数异常" not in out2


def test_name_is_optional_not_required():
    reg = RegistrationSession(notifier=MockNotifier())
    reg.record(plate="沪A1", company="蓝色鲸鱼", reason="送货", phone="13800138000")
    assert reg.info.is_complete()  # name not required for completion
    reg2 = RegistrationSession(notifier=MockNotifier())
    out = reg2.record(name="张师傅")
    assert reg2.info.name == "张师傅" and "张师傅" not in (out or "")  # stored, not echoed weirdly
