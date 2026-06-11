import json

from visitor_agent.access import check_access, load_access_list, make_access_checker


def _write(tmp_path):
    p = tmp_path / "access.json"
    p.write_text(
        json.dumps(
            {
                "blacklist": [
                    {"plate": "沪A00000", "reason": "欠费"},
                    {"phone": "13900000000", "name": "推销", "reason": "骚扰"},
                ],
                "whitelist": [
                    {"plate": "粤B88888", "name": "王总", "reason": "VIP"},
                    {"phone": "13800138000", "name": "李经理"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return str(p)


def test_disabled_when_no_file():
    assert make_access_checker("") is None
    assert make_access_checker("/no/such/file.json") is None


def test_blacklist_by_plate(tmp_path):
    check = make_access_checker(_write(tmp_path))
    m = check("沪A00000", None)
    assert m and m["status"] == "blacklist" and m["matched_on"] == "plate"
    assert m["reason"] == "欠费"


def test_whitelist_by_phone(tmp_path):
    check = make_access_checker(_write(tmp_path))
    m = check(None, "13800138000")
    assert m and m["status"] == "whitelist" and m["name"] == "李经理"


def test_blacklist_beats_whitelist(tmp_path):
    # plate is whitelisted (粤B88888) but phone is blacklisted -> blacklist wins.
    check = make_access_checker(_write(tmp_path))
    m = check("粤B88888", "13900000000")
    assert m["status"] == "blacklist"


def test_normalization_matches(tmp_path):
    # spoken province name + spaces still match the normalized "沪A00000".
    check = make_access_checker(_write(tmp_path))
    assert check("上海A 000 00", None)["status"] == "blacklist"


def test_no_match_returns_none(tmp_path):
    check = make_access_checker(_write(tmp_path))
    assert check("京C11111", "13700000000") is None


def test_entries_without_plate_or_phone_are_dropped(tmp_path):
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"blacklist": [{"name": "无标识"}]}), encoding="utf-8")
    access = load_access_list(str(p))
    assert access["blacklist"] == []


def test_check_access_empty_list():
    assert check_access("沪A1", "13800138000", {"blacklist": [], "whitelist": []}) is None
