import pytest


def _reload_settings(monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    from visitor_agent import config

    config.get_settings.cache_clear()


def test_gate_stub_by_default(monkeypatch):
    # ensure no Hikvision config
    monkeypatch.delenv("HIKVISION_URL", raising=False)
    _reload_settings(monkeypatch)
    from visitor_agent.notify import gate

    assert gate.open_gate(visit_id=1, plate="沪A1") is True  # stub, no network


def test_gate_isapi_when_configured(monkeypatch):
    _reload_settings(
        monkeypatch,
        HIKVISION_URL="http://192.168.1.64",
        HIKVISION_USER="admin",
        HIKVISION_PASSWORD="pw",
        HIKVISION_CHANNEL="2",
    )
    import httpx

    calls = {}

    class FakeResp:
        status_code = 200

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def put(self, url, content=None, auth=None):
            calls["url"] = url
            calls["body"] = content
            return FakeResp()

    monkeypatch.setattr(httpx, "Client", lambda *a, **k: FakeClient())
    monkeypatch.setattr(httpx, "DigestAuth", lambda u, p: ("auth", u, p))

    from visitor_agent.notify import gate

    ok = gate.open_gate(visit_id=5, plate="沪A12345")
    assert ok is True
    assert calls["url"].endswith("/ISAPI/ITC/Entrance/barrierGateCtrl/channels/2")
    assert "open" in calls["body"]


def test_isapi_payload_shape():
    from visitor_agent.notify import gate

    path, body = gate.isapi_barrier_payload(3)
    assert path.endswith("/channels/3") and "<cmd>open</cmd>" in body
