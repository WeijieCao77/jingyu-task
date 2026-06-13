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


def test_count_by_released_status(temp_db):
    from visitor_agent import guard_query

    repo = temp_db
    repo.create_visit({"plate": "沪A1"}, "s1")
    repo.create_visit({"plate": "沪A2"}, "s2")
    repo.mark_confirmed("s2")  # only this one released

    assert '"count": 2' in guard_query.run_tool("count_visits", {})
    assert '"count": 1' in guard_query.run_tool("count_visits", {"status": "confirmed"})
    assert '"count": 1' in guard_query.run_tool("count_visits", {"status": "pending"})


def test_guard_query_model_tiering(temp_db, monkeypatch):
    from visitor_agent import config, guard_query

    monkeypatch.setenv("GUARD_QUERY_MODEL", "gpt-4o")
    config.get_settings.cache_clear()
    captured = {}

    def fake_openai(q, model, max_steps, history=None):
        captured["model"] = model
        return "ok"

    monkeypatch.setattr(guard_query, "_answer_openai", fake_openai)
    assert guard_query.answer_question("多少车") == "ok"
    assert captured["model"] == "gpt-4o"   # used GUARD_QUERY_MODEL, not LLM_MODEL


def test_clean_history_filters_bad_turns():
    from visitor_agent.guard_query import _clean_history

    h = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"},
         {"role": "system", "content": "x"}, {"role": "user", "content": ""},
         {"role": "user"}]
    assert _clean_history(h) == [{"role": "user", "content": "a"},
                                 {"role": "assistant", "content": "b"}]
    assert _clean_history(None) == []
