"""End-to-end-ish tests that exercise the real LiveNotifier + DB path offline.

With NOTIFY_CHANNEL=none the notifier does no network I/O (the dashboard is the
guard console), so the whole register -> persist -> recognize loop is testable
without any API keys.
"""

import asyncio

import pytest


@pytest.fixture()
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/visits.db")
    monkeypatch.setenv("NOTIFY_CHANNEL", "none")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8080")
    from visitor_agent import config

    config.get_settings.cache_clear()
    cfg = config.get_settings()
    from visitor_agent.db import repo

    repo.init_db(cfg.database_url)
    return cfg


def test_register_persists_and_then_recognizes_returning(settings):
    from visitor_agent.db import repo
    from visitor_agent.session_logic import (
        LiveNotifier,
        RegistrationSession,
        make_db_lookup,
    )

    # First visit — full registration via the real LiveNotifier (no network).
    reg = RegistrationSession(notifier=LiveNotifier(settings), tz=settings.timezone)
    reg.record(plate="沪A12345", company="蓝色鲸鱼", reason="送货", phone="13800138000",
               name="张师傅")
    asyncio.run(reg.complete())
    assert reg.completed
    assert len(repo.recent_visits()) == 1
    v = repo.recent_visits()[0]
    assert v.plate == "沪A12345" and v.name == "张师傅" and v.entry_time
    assert v.confirm_token and v.status == "pending"

    # Second visit — same person should be recognized (returning), prefilled.
    reg2 = RegistrationSession(
        notifier=LiveNotifier(settings),
        lookup_returning=make_db_lookup(),
        tz=settings.timezone,
    )
    out = reg2.record(plate="沪A12345")
    assert "回访识别" in out
    assert reg2.info.company == "蓝色鲸鱼" and reg2.info.name == "张师傅"


def test_concurrent_sessions_are_isolated(settings):
    from visitor_agent.session_logic import LiveNotifier, RegistrationSession

    a = RegistrationSession(notifier=LiveNotifier(settings))
    b = RegistrationSession(notifier=LiveNotifier(settings))
    a.record(plate="沪A11111", company="甲公司")
    b.record(plate="浙B22222", company="乙公司")
    # No shared mutable state between calls.
    assert a.info.plate == "沪A11111" and a.info.company == "甲公司"
    assert b.info.plate == "浙B22222" and b.info.company == "乙公司"


def test_full_dashboard_events_emitted(settings):
    """A completed registration emits the dashboard timeline events to the DB."""
    import json

    from visitor_agent.db import repo
    from visitor_agent.session_logic import LiveNotifier, RegistrationSession

    events = []

    def sink(kind, role, text, payload):
        repo.log_event("call-x", kind, role=role, text=text,
                       payload=json.dumps(payload) if payload else None)
        events.append(kind)

    reg = RegistrationSession(notifier=LiveNotifier(settings), event_sink=sink,
                              tz=settings.timezone)
    reg.record(plate="沪A1", company="蓝色鲸鱼", reason="送货", phone="13800138000")
    asyncio.run(reg.complete())
    assert "slot" in events and "completed" in events and "pushed" in events
    assert {e.kind for e in repo.events_after(0)} >= {"slot", "completed", "pushed"}
