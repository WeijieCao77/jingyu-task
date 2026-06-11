import json

from visitor_agent import roster
from visitor_agent.slots import normalize_plate


def test_load_roster_strings_and_objects(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps([
        "顺丰速运",
        {"name": "蓝色鲸鱼科技", "aliases": ["蓝色鲸鱼", "蓝鲸"]},
    ], ensure_ascii=False), encoding="utf-8")
    pairs = roster.load_roster(str(p))
    officials = {off for _, off in pairs}
    assert "顺丰速运" in officials and "蓝色鲸鱼科技" in officials
    # alias maps to official
    assert ("蓝鲸", "蓝色鲸鱼科技") in pairs


def test_match_corrects_homophone():
    pairs = [("蓝色鲸鱼科技", "蓝色鲸鱼科技"), ("顺丰速运", "顺丰速运")]
    name, score = roster.match_company("蓝色金鱼", pairs)   # mis-heard 鲸->金
    assert name == "蓝色鲸鱼科技" and score >= 0.55


def test_match_alias_and_exact():
    pairs = [("蓝色鲸鱼", "蓝色鲸鱼科技"), ("蓝色鲸鱼科技", "蓝色鲸鱼科技")]
    assert roster.match_company("蓝色鲸鱼", pairs)[0] == "蓝色鲸鱼科技"
    assert roster.match_company("蓝色鲸鱼科技", pairs) == ("蓝色鲸鱼科技", 1.0)


def test_no_match_below_threshold():
    pairs = [("蓝色鲸鱼科技", "蓝色鲸鱼科技")]
    name, _ = roster.match_company("完全不相关的公司", pairs, threshold=0.6)
    assert name is None


def test_matcher_disabled_without_roster():
    assert roster.make_matcher("", 0.55) is None
    assert roster.make_matcher("/nonexistent/path.json", 0.55) is None


def test_registration_session_applies_roster():
    from visitor_agent.session_logic import MockNotifier, RegistrationSession

    pairs = [("蓝色鲸鱼科技", "蓝色鲸鱼科技")]
    matcher = lambda t: roster.match_company(t, pairs)  # noqa: E731
    reg = RegistrationSession(notifier=MockNotifier(), roster_match=matcher)
    out = reg.record(company="蓝色金鱼")
    assert reg.info.company == "蓝色鲸鱼科技"   # corrected
    assert "已匹配名单" in out                  # AI told to confirm


def test_plate_province_name_normalized():
    assert normalize_plate("广东A12345") == "粤A12345"
    assert normalize_plate("上海A12345") == "沪A12345"
    # already-abbreviated still works
    assert normalize_plate("沪A12345") == "沪A12345"
