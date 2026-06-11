def test_default_voice_mode_is_realtime(monkeypatch):
    monkeypatch.delenv("VOICE_MODE", raising=False)
    from visitor_agent import config

    # Ignore any on-disk .env so the *code* default is what's asserted.
    monkeypatch.setitem(config.Settings.model_config, "env_file", None)
    config.get_settings.cache_clear()
    assert config.get_settings().voice_mode == "realtime"
    config.get_settings.cache_clear()


def test_voice_mode_env_override(monkeypatch):
    monkeypatch.setenv("VOICE_MODE", "realtime")
    monkeypatch.setenv("REALTIME_VOICE", "cedar")
    from visitor_agent import config

    config.get_settings.cache_clear()
    s = config.get_settings()
    assert s.voice_mode == "realtime" and s.realtime_voice == "cedar"
    config.get_settings.cache_clear()


def test_build_realtime_is_callable():
    # symbol exists and is importable (construction needs a live key, not asserted here)
    from visitor_agent.providers import build_realtime

    assert callable(build_realtime)
