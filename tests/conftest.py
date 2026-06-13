"""Shared test fixtures.

Hermetic config: tests must NOT read the developer's real `.env` from disk. A
local `.env` with e.g. `GUARD_ACCESS_KEY` or `LIVEKIT_*` set would otherwise leak
into `Settings()` and break the web/auth tests (they'd hit the guard gate, or
`/token` would think LiveKit is configured). Disabling `env_file` for every test
makes the suite depend only on each test's own monkeypatched env + defaults.
"""

import pytest

from visitor_agent import config


@pytest.fixture(autouse=True)
def _hermetic_settings(monkeypatch):
    monkeypatch.setitem(config.Settings.model_config, "env_file", None)
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()
