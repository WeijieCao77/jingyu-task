from visitor_agent.notify.wecom import build_markdown, build_payload


def test_build_markdown_has_all_fields_and_link():
    visit = {
        "plate": "沪A12345",
        "company": "蓝色鲸鱼科技",
        "reason": "送货",
        "phone": "13800138000",
        "entry_time": "2025-04-13 14:30",
    }
    md = build_markdown(visit, "https://x.test/confirm?token=abc")
    for v in visit.values():
        assert v in md
    assert "确认放行" in md
    assert "https://x.test/confirm?token=abc" in md


def test_build_payload_shape():
    payload = build_payload({"plate": "沪A1"}, "https://x/confirm?token=t")
    assert payload["msgtype"] == "markdown"
    assert "content" in payload["markdown"]


def test_returning_badge():
    md = build_markdown({"plate": "沪A1", "returning": True}, "https://x/c?token=t")
    assert "回访车辆" in md
