import json

from visitor_agent.tenant import apply_tenant, load_tenants, resolve_tenant


def _write(tmp_path):
    p = tmp_path / "tenants.json"
    p.write_text(json.dumps({"tenants": [
        {"name": "园区A", "numbers": ["+15863257270"],
         "roster_path": "roster.A.json", "guard_access_key": "keyA",
         "notify_channel": "telegram"},
        {"name": "园区B", "numbers": ["+8657188889999"],
         "access_list_path": "access.B.json"},
    ]}, ensure_ascii=False), encoding="utf-8")
    return str(p)


def test_disabled_when_no_file():
    assert load_tenants("") is None
    assert load_tenants("/no/such.json") is None
    assert resolve_tenant("", "+1...") is None


def test_resolve_exact_and_suffix(tmp_path):
    path = _write(tmp_path)
    assert resolve_tenant(path, "+15863257270")["name"] == "园区A"
    # tolerant of prefix differences (raw vs +): suffix match
    assert resolve_tenant(path, "15863257270")["name"] == "园区A"
    assert resolve_tenant(path, "+8657188889999")["name"] == "园区B"
    assert resolve_tenant(path, "+1999")  is None


def test_apply_tenant_overrides_cfg(tmp_path):
    from visitor_agent.config import Settings

    cfg = Settings(roster_path="global.json", guard_access_key="global")
    tenant = resolve_tenant(_write(tmp_path), "+15863257270")
    eff = apply_tenant(cfg, tenant)
    assert eff.roster_path == "roster.A.json"        # overridden
    assert eff.guard_access_key == "keyA"            # overridden
    assert eff.notify_channel == "telegram"
    assert eff.database_url == cfg.database_url       # untouched falls back to global
    # no tenant → unchanged object
    assert apply_tenant(cfg, None) is cfg
