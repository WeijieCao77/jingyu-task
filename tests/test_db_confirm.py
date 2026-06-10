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


def test_create_get_confirm(temp_db):
    repo = temp_db
    info = {
        "plate": "沪A12345",
        "company": "蓝色鲸鱼",
        "reason": "送货",
        "phone": "13800138000",
        "entry_time": "2025-04-13 14:30",
    }
    visit = repo.create_visit(info, confirm_token="tok123", status="pending")
    assert visit.id is not None

    fetched = repo.get_visit_by_token("tok123")
    assert fetched.plate == "沪A12345"
    assert fetched.status == "pending"

    confirmed = repo.mark_confirmed("tok123")
    assert confirmed.status == "confirmed"
    assert confirmed.confirmed_at is not None

    # idempotent
    again = repo.mark_confirmed("tok123")
    assert again.status == "confirmed"


def test_returning_lookup(temp_db):
    repo = temp_db
    repo.create_visit({"plate": "沪A12345", "company": "蓝色鲸鱼", "reason": "送货"}, "t1")
    found = repo.find_recent_visit_by_plate("沪A12345")
    assert found is not None and found.company == "蓝色鲸鱼"
    assert repo.find_recent_visit_by_plate("浙B00000") is None


def test_recognize_profile(temp_db):
    repo = temp_db
    # 张师傅: phone 13800138000, visited twice in 沪A12345
    repo.create_visit(
        {"plate": "沪A12345", "company": "蓝色鲸鱼", "reason": "送货",
         "phone": "13800138000", "name": "张师傅"}, "r1")
    repo.create_visit(
        {"plate": "沪A12345", "company": "蓝色鲸鱼", "reason": "送货",
         "phone": "13800138000", "name": "张师傅"}, "r2")

    # same person, same car → plate+phone
    p = repo.recognize(plate="沪A12345", phone="13800138000")
    assert p["match_type"] == "plate+phone" and p["visit_count"] == 2
    assert p["name"] == "张师傅" and p["last_company"] == "蓝色鲸鱼"

    # same person, different car → phone
    p2 = repo.recognize(plate="浙B00000", phone="13800138000")
    assert p2["match_type"] == "phone"

    # same car, different person → plate (vehicle known)
    p3 = repo.recognize(plate="沪A12345", phone="13999999999")
    assert p3["match_type"] == "plate"

    # unknown both
    assert repo.recognize(plate="京A00000", phone="13700000000") is None


def test_confirm_endpoint_opens_gate(temp_db, monkeypatch):
    from fastapi.testclient import TestClient

    from visitor_agent.notify import gate
    from visitor_agent.web import server as srv

    importlib.reload(srv)  # rebind app to current settings

    opened = {}
    monkeypatch.setattr(
        gate, "open_gate", lambda **kw: opened.update(kw) or True
    )
    monkeypatch.setattr(srv.gate, "open_gate", gate.open_gate)

    temp_db.create_visit({"plate": "沪A12345", "company": "蓝色鲸鱼"}, "tokweb")

    client = TestClient(srv.app)
    resp = client.get("/confirm", params={"token": "tokweb"})
    assert resp.status_code == 200
    assert "已放行" in resp.text
    assert opened.get("plate") == "沪A12345"

    # invalid token
    bad = client.get("/confirm", params={"token": "nope"})
    assert "链接无效" in bad.text
