import importlib

import pytest


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path}/visits.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("NOTIFY_CHANNEL", "none")
    from visitor_agent import config

    config.get_settings.cache_clear()
    from visitor_agent.db import repo

    repo.init_db(db_url)
    return repo


def test_local_confirm_button(temp_db, monkeypatch):
    from fastapi.testclient import TestClient

    from visitor_agent.notify import gate
    from visitor_agent.web import server as srv

    importlib.reload(srv)
    opened = {}
    monkeypatch.setattr(srv.gate, "open_gate", lambda **kw: opened.update(kw) or True)

    visit = temp_db.create_visit({"plate": "沪A12345", "company": "蓝色鲸鱼"}, "tok-local")

    client = TestClient(srv.app)
    resp = client.post(f"/api/confirm/{visit.id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"
    assert opened.get("plate") == "沪A12345"

    # gate/confirmed events logged for the dashboard
    kinds = {e.kind for e in temp_db.events_after(0)}
    assert "confirmed" in kinds and "gate" in kinds

    # unknown id -> 404
    assert client.post("/api/confirm/9999").status_code == 404


def test_notify_none_returns_true(temp_db):
    import asyncio

    from visitor_agent.config import get_settings
    from visitor_agent.notify import dispatch

    ok = asyncio.run(dispatch.push(get_settings(), {"plate": "沪A1"}, "http://x/confirm?token=t"))
    assert ok is True


def test_guard_access_key_gate(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    db_url = f"sqlite:///{tmp_path}/v.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("GUARD_ACCESS_KEY", "s3cret")
    from visitor_agent import config

    config.get_settings.cache_clear()
    from visitor_agent.db import repo

    repo.init_db(db_url)
    from visitor_agent.web import server as srv

    importlib.reload(srv)
    client = TestClient(srv.app)

    assert client.get("/voice").status_code == 200            # visitor page public
    r = client.get("/dashboard", follow_redirects=False)       # guard page → login
    assert r.status_code == 303 and "/login" in r.headers["location"]
    assert client.get("/api/visits").status_code == 401        # guard API blocked
    assert client.get("/api/visits", headers={"X-Guard-Key": "s3cret"}).status_code == 200
    # wrong key → bounced; correct key → cookie set, then dashboard works
    assert "/login" in client.get("/login/set", params={"key": "nope"},
                                  follow_redirects=False).headers["location"]
    client.get("/login/set", params={"key": "s3cret"}, follow_redirects=False)
    assert client.get("/dashboard").status_code == 200
    config.get_settings.cache_clear()


def test_api_query_structured(temp_db):
    from fastapi.testclient import TestClient

    from visitor_agent.web import server as srv

    importlib.reload(srv)
    temp_db.create_visit({"plate": "沪A1", "company": "蓝色鲸鱼"}, "q1")
    temp_db.create_visit({"plate": "沪A2", "company": "蓝色鲸鱼"}, "q2")
    temp_db.create_visit({"plate": "沪B9", "company": "别家"}, "q3")
    temp_db.mark_confirmed("q2")  # one released

    client = TestClient(srv.app)
    d = client.get("/api/query", params={"range": "all"}).json()
    assert d["count"] == 3 and d["released"] == 1 and len(d["visits"]) == 3
    assert client.get("/api/query", params={"range": "all", "company": "蓝色鲸鱼"}).json()["count"] == 2
    assert client.get("/api/query", params={"range": "all", "status": "confirmed"}).json()["count"] == 1


def test_ask_page_and_query_endpoint(temp_db, monkeypatch):
    from fastapi.testclient import TestClient

    from visitor_agent import guard_query
    from visitor_agent.web import server as srv

    importlib.reload(srv)
    client = TestClient(srv.app)

    # data center page renders both modes
    page = client.get("/ask")
    assert page.status_code == 200 and "门卫数据中心" in page.text and "筛选查询" in page.text

    # endpoint forwards the question + prior turns (history) to the agent
    seen = {}

    def fake_answer(question, history=None, **kw):
        seen["q"], seen["h"] = question, history
        return "本月已放行 12 辆。"

    monkeypatch.setattr(guard_query, "answer_question", fake_answer)
    monkeypatch.setattr(srv, "answer_question", fake_answer, raising=False)

    body = {"question": "那上个月呢？",
            "history": [{"role": "user", "content": "这个月放行多少"},
                        {"role": "assistant", "content": "10 辆"}]}
    r = client.post("/guard/query", json=body)
    assert r.status_code == 200 and "已放行" in r.json()["answer"]
    assert seen["q"] == "那上个月呢？" and len(seen["h"]) == 2
