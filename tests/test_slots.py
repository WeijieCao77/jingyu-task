from visitor_agent.slots import VisitorInfo, normalize_phone, normalize_plate


def test_normalize_plate():
    assert normalize_plate("沪A 123 45") == "沪A12345"
    assert normalize_plate("苏E·9F8K7") == "苏E9F8K7"
    assert normalize_plate("沪a12345") == "沪A12345"
    assert normalize_plate(None) is None


def test_normalize_phone():
    assert normalize_phone("138 0013 8000") == "13800138000"
    assert normalize_phone("我的号码是13912345678哦") == "13912345678"
    assert normalize_phone(None) is None


def test_incremental_fill_and_completeness():
    info = VisitorInfo()
    assert not info.is_complete()
    info.update(plate="沪A12345", company="蓝色鲸鱼", reason="送货")
    assert info.missing_fields() == ["phone"]
    info.update(phone="13800138000")
    assert info.is_complete()
    assert info.human_summary() == "沪A12345，蓝色鲸鱼，送货"


def test_partial_update_does_not_overwrite_with_empty():
    info = VisitorInfo(company="蓝色鲸鱼")
    info.update(company=None)
    assert info.company == "蓝色鲸鱼"


def test_entry_time_stamped():
    info = VisitorInfo()
    ts = info.stamp_entry_time("Asia/Shanghai")
    assert len(ts) == 16 and ts[4] == "-" and ts[13] == ":"
