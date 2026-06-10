import pytest


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path}/visits.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    from visitor_agent import config

    config.get_settings.cache_clear()
    from visitor_agent.db import repo

    repo.init_db(db_url)
    return repo


def test_event_log_and_after(temp_db):
    repo = temp_db
    assert repo.latest_event_id() == 0
    e1 = repo.log_event("call1", "call_started", text="来电")
    e2 = repo.log_event("call1", "user", role="user", text="沪A12345")
    assert e2.id > e1.id
    after = repo.events_after(e1.id)
    assert len(after) == 1 and after[0].text == "沪A12345"
    assert repo.latest_event_id() == e2.id


def test_dashboard_and_visits_api(temp_db, monkeypatch):
    import importlib

    from fastapi.testclient import TestClient

    from visitor_agent.web import server as srv

    importlib.reload(srv)

    temp_db.create_visit({"plate": "沪A12345", "company": "蓝色鲸鱼", "reason": "送货"}, "tk")
    client = TestClient(srv.app)

    page = client.get("/dashboard")
    assert page.status_code == 200 and "门卫控制台" in page.text

    visits = client.get("/api/visits").json()
    assert any(v["plate"] == "沪A12345" for v in visits)


def test_confirm_logs_events(temp_db, monkeypatch):
    import importlib

    from fastapi.testclient import TestClient

    from visitor_agent.web import server as srv

    importlib.reload(srv)
    visit = temp_db.create_visit({"plate": "沪A1", "company": "蓝色鲸鱼"}, "tok-ev")

    client = TestClient(srv.app)
    client.get("/confirm", params={"token": "tok-ev"})

    events = temp_db.events_after(0)
    kinds = {e.kind for e in events}
    assert "confirmed" in kinds and "gate" in kinds
