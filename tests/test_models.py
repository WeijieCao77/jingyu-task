def test_llm_base_url_default_empty(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    from visitor_agent import config

    config.get_settings.cache_clear()
    assert config.get_settings().llm_base_url == ""


def test_llm_base_url_override(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("LLM_MODEL", "anthropic/claude-3.5-sonnet")
    from visitor_agent import config

    config.get_settings.cache_clear()
    s = config.get_settings()
    assert s.llm_base_url.endswith("/api/v1")
    assert s.llm_model == "anthropic/claude-3.5-sonnet"
    config.get_settings.cache_clear()
