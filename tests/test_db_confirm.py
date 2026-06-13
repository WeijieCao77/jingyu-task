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


def test_resolve_sqlite_url_anchors_relative():
    from pathlib import Path

    from visitor_agent.db.repo import _resolve_sqlite_url

    out = _resolve_sqlite_url("sqlite:///./data/visits.db")
    p = out[len("sqlite:///"):]
    assert Path(p).is_absolute() and p.endswith("visits.db")  # CWD-independent now
    # already-absolute + non-sqlite pass through unchanged
    assert _resolve_sqlite_url("sqlite:////abs/x.db") == "sqlite:////abs/x.db"
    assert _resolve_sqlite_url("postgresql://u@h/db") == "postgresql://u@h/db"


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


def test_create_visit_stores_room_and_access(temp_db):
    repo = temp_db
    repo.create_visit(
        {"plate": "沪A1", "access_status": "whitelist", "room": "voice-demo"}, "tkr"
    )
    d = repo.get_visit_by_token("tkr").to_dict()
    assert d["access_status"] == "whitelist" and d["room"] == "voice-demo"


def test_whitelist_auto_pass_opens_gate(temp_db, monkeypatch):
    import asyncio
    import types

    from visitor_agent.notify import gate
    from visitor_agent.session_logic import LiveNotifier

    opened = {}
    monkeypatch.setattr(gate, "open_gate", lambda **kw: opened.update(kw) or True)

    s = types.SimpleNamespace(
        public_base_url="http://x", notify_channel="none", auto_pass_whitelist=True
    )
    asyncio.run(LiveNotifier(s).notify({"plate": "粤B88888", "access_status": "whitelist"}))
    assert temp_db.recent_visits()[0].status == "confirmed"  # auto-passed
    assert opened.get("plate") == "粤B88888"


def test_whitelist_not_auto_passed_when_disabled(temp_db):
    import asyncio
    import types

    from visitor_agent.session_logic import LiveNotifier

    s = types.SimpleNamespace(
        public_base_url="http://x", notify_channel="none", auto_pass_whitelist=False
    )
    asyncio.run(LiveNotifier(s).notify({"plate": "粤B88888", "access_status": "whitelist"}))
    assert temp_db.recent_visits()[0].status == "pending"  # guard still confirms


def test_dial_guard_no_op_when_unconfigured(temp_db):
    import asyncio
    import types

    from visitor_agent.sip_out import dial_guard

    # missing trunk/number/livekit → returns False, never raises
    s = types.SimpleNamespace(guard_dial_number="", sip_outbound_trunk_id="",
                              livekit_url="", livekit_api_key="", livekit_api_secret="")
    assert asyncio.run(dial_guard(s, "call-1")) is False
    # configured but livekit pkg absent here → caught → False (best-effort)
    s2 = types.SimpleNamespace(guard_dial_number="+8613800138000",
                               sip_outbound_trunk_id="ST_x", livekit_url="wss://x.livekit.cloud",
                               livekit_api_key="k", livekit_api_secret="s")
    assert asyncio.run(dial_guard(s2, "call-1")) is False


def test_dial_guard_endpoint_unconfigured(temp_db):
    from fastapi.testclient import TestClient

    from visitor_agent.web import server as srv

    importlib.reload(srv)
    r = TestClient(srv.app).post("/api/dial_guard", params={"room": "call-1"})
    assert r.status_code == 400 and r.json()["ok"] is False


def test_notify_room_approved_is_safe_without_livekit(temp_db, monkeypatch):
    # LiveKit configured but the package isn't installed here → must be a silent
    # no-op, never raising into the confirm/gate flow (FR-2 best-effort).
    monkeypatch.setenv("LIVEKIT_URL", "wss://x.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "k")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "s")
    from visitor_agent import config

    config.get_settings.cache_clear()
    from visitor_agent.web import server as srv

    importlib.reload(srv)
    srv._notify_room_approved("voice-demo")  # no raise
    srv._notify_room_approved(None)


def test_blacklist_cannot_be_released(temp_db, monkeypatch):
    from fastapi.testclient import TestClient

    from visitor_agent.notify import gate
    from visitor_agent.web import server as srv

    importlib.reload(srv)
    opened = {}
    monkeypatch.setattr(srv.gate, "open_gate", lambda **kw: opened.update(kw) or True)

    v = temp_db.create_visit(
        {"plate": "沪A00000", "access_status": "blacklist"}, "tokbl"
    )
    client = TestClient(srv.app)

    # link path: registered but refused, gate not opened, still pending
    page = client.get("/confirm", params={"token": "tokbl"})
    assert "禁止放行" in page.text
    # dashboard button path: 403
    api = client.post(f"/api/confirm/{v.id}")
    assert api.status_code == 403 and "黑名单" in api.json()["message"]

    assert not opened  # gate never fired
    assert temp_db.get_visit_by_id(v.id).status == "pending"


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
