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


def test_count_and_hours(temp_db):
    from visitor_agent import guard_query

    repo = temp_db
    repo.create_visit({"plate": "沪A1", "company": "蓝色鲸鱼", "entry_time": "2025-04-13 09:30"}, "a")
    repo.create_visit({"plate": "沪A2", "company": "蓝色鲸鱼", "entry_time": "2025-04-13 09:45"}, "b")
    repo.create_visit({"plate": "沪A3", "company": "别家", "entry_time": "2025-04-13 14:10"}, "c")

    assert guard_query.run_tool("count_visits", {}) == '{"count": 3}'
    out = guard_query.run_tool("count_visits", {"company": "蓝色鲸鱼"})
    assert '"count": 2' in out

    hours = guard_query.run_tool("busiest_hours", {})
    assert '"9": 2' in hours and '"14": 1' in hours


def test_list_visits(temp_db):
    from visitor_agent import guard_query

    temp_db.create_visit({"plate": "沪A12345", "company": "蓝色鲸鱼"}, "x")
    out = guard_query.run_tool("list_visits", {"plate": "沪A12345"})
    assert "沪A12345" in out
