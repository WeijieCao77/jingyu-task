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


def test_ask_page_and_query_endpoint(temp_db, monkeypatch):
    from fastapi.testclient import TestClient

    from visitor_agent import guard_query
    from visitor_agent.web import server as srv

    importlib.reload(srv)
    client = TestClient(srv.app)

    # conversational query page renders
    page = client.get("/ask")
    assert page.status_code == 200 and "门卫数据助手" in page.text

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
