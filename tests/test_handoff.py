import importlib


def test_request_human_emits_escalation_event():
    from visitor_agent.session_logic import MockNotifier, RegistrationSession

    events = []
    reg = RegistrationSession(
        notifier=MockNotifier(),
        event_sink=lambda kind, role, text, payload: events.append((kind, payload)),
    )
    reg.record(plate="沪A12345")
    out = reg.request_human(reason="访客要求真人")
    assert reg.escalated
    assert "门卫师傅" in out
    kinds = [k for k, _ in events]
    assert "escalation" in kinds
    # payload carries the reason + collected info
    payload = next(p for k, p in events if k == "escalation")
    assert payload["reason"] == "访客要求真人" and payload["plate"] == "沪A12345"


def test_guard_call_page_served(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path}/visits.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    from visitor_agent import config

    config.get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from visitor_agent.web import server as srv

    importlib.reload(srv)
    page = TestClient(srv.app).get("/guard_call")
    assert page.status_code == 200 and "保安介入通话" in page.text
