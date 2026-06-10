import importlib

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


def test_visitor_profiles_aggregates_by_person(temp_db):
    repo = temp_db
    # 张师傅 (phone A) visited 3 times, two plates, confirmed twice
    repo.create_visit({"plate": "沪A1", "company": "蓝色鲸鱼", "reason": "送货",
                       "phone": "13800138000", "name": "张师傅"}, "a1", status="confirmed")
    repo.create_visit({"plate": "沪A1", "company": "蓝色鲸鱼", "reason": "送货",
                       "phone": "13800138000", "name": "张师傅"}, "a2", status="confirmed")
    repo.create_visit({"plate": "浙B2", "company": "别家", "reason": "拜访",
                       "phone": "13800138000"}, "a3", status="pending")
    # someone else once
    repo.create_visit({"plate": "京C3", "company": "蓝色鲸鱼", "phone": "13900139000"}, "b1")

    profiles = repo.visitor_profiles()
    top = profiles[0]
    assert top["phone"] == "13800138000"
    assert top["visit_count"] == 3 and top["confirmed_count"] == 2
    assert top["name"] == "张师傅"
    assert set(top["plates"]) == {"沪A1", "浙B2"}
    assert "蓝色鲸鱼" in top["companies"] and "别家" in top["companies"]

    # min_visits filter
    only_freq = repo.visitor_profiles(min_visits=2)
    assert all(p["visit_count"] >= 2 for p in only_freq)


def test_admin_page_and_api(temp_db):
    from fastapi.testclient import TestClient

    from visitor_agent.web import server as srv

    importlib.reload(srv)
    temp_db.create_visit({"plate": "沪A1", "company": "蓝色鲸鱼", "phone": "13800138000"}, "x")
    client = TestClient(srv.app)

    assert "常客名单" in client.get("/admin").text
    data = client.get("/api/profiles").json()
    assert any(p["phone"] == "13800138000" for p in data)
