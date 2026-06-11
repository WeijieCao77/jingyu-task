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


def test_voice_page_and_token(temp_db, monkeypatch):
    import importlib

    from fastapi.testclient import TestClient

    # configure LiveKit so /token can mint a JWT
    monkeypatch.setenv("LIVEKIT_URL", "wss://demo.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "APIxxxx")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "secretsecretsecretsecret")
    from visitor_agent import config

    config.get_settings.cache_clear()
    from visitor_agent.web import server as srv

    importlib.reload(srv)
    client = TestClient(srv.app)

    voice = client.get("/voice").text
    assert "访客登记" in voice and "AI 门卫" in voice
    assert "扫码登记访客" in client.get("/qr").text

    tok = client.get("/token", params={"room": "voice-demo", "identity": "v1"}).json()
    assert tok["url"].startswith("wss://") and tok["token"].count(".") == 2  # JWT


def test_token_requires_config(temp_db, monkeypatch):
    import importlib

    from fastapi.testclient import TestClient

    for k in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"):
        monkeypatch.delenv(k, raising=False)
    from visitor_agent import config

    # Don't let a real local .env (with LIVEKIT_* set) leak in and make /token
    # think LiveKit is configured — this test asserts the unconfigured path.
    monkeypatch.setitem(config.Settings.model_config, "env_file", None)
    config.get_settings.cache_clear()
    from visitor_agent.web import server as srv

    importlib.reload(srv)
    resp = TestClient(srv.app).get("/token")
    assert resp.status_code == 400


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
