"""Multi-tenant configuration (productization · phase 1).

A productized SaaS serves many parks from one deployment: each call is routed to
the right **tenant** by the number that was DIALED (the SIP `trunkPhoneNumber`),
and each tenant has its own roster, blacklist/whitelist, notification channel,
guard key/phones, public URL, etc. So "one downloaded product, many customers",
each isolated.

Disabled unless `TENANTS_PATH` points at a JSON file → the base single-tenant
demo is completely unchanged. File format (see `tenants.example.json`):

    {
      "tenants": [
        {
          "name": "蓝色鲸鱼园区",
          "numbers": ["+15863257270"],          // 入园电话（被叫号码）
          "roster_path": "roster.bluewhale.json",
          "access_list_path": "access.bluewhale.json",
          "notify_channel": "telegram",
          "telegram_bot_token": "...", "telegram_chat_id": "...",
          "guard_access_key": "...", "guard_phones": "+8613...",
          "public_base_url": "https://bluewhale.example.com"
        }
      ]
    }
"""

from __future__ import annotations

import json
import os
import re

# Fields a tenant may override on the global Settings for the duration of a call.
_OVERRIDE_KEYS = (
    "roster_path", "roster_threshold", "access_list_path", "auto_pass_whitelist",
    "notify_channel", "telegram_bot_token", "telegram_chat_id",
    "wecom_webhook_url", "discord_webhook_url",
    "guard_access_key", "guard_phones", "public_base_url",
    "voice_mode", "guard_query_model", "timezone",
)


def _digits(s: str | None) -> str:
    return re.sub(r"\D", "", s or "")


class Tenants:
    """Loaded tenant table, indexed by the dialed number (digits only)."""

    def __init__(self, by_number: dict[str, dict]) -> None:
        self._by_number = by_number

    def resolve(self, called_number: str | None) -> dict | None:
        """Return the tenant for the dialed number, tolerant of +1 / 1 / raw
        prefixes (exact digits, else a suffix match)."""
        d = _digits(called_number)
        if not d:
            return None
        if d in self._by_number:
            return self._by_number[d]
        for num, tenant in self._by_number.items():
            if num.endswith(d) or d.endswith(num):
                return tenant
        return None


def load_tenants(path: str | None) -> Tenants | None:
    """Build the tenant table, or None if no/empty file (single-tenant mode)."""
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    by_number: dict[str, dict] = {}
    for tenant in data.get("tenants", []) or []:
        for num in tenant.get("numbers", []) or []:
            key = _digits(num)
            if key:
                by_number[key] = tenant
    return Tenants(by_number) if by_number else None


def resolve_tenant(path: str | None, called_number: str | None) -> dict | None:
    tenants = load_tenants(path)
    return tenants.resolve(called_number) if tenants else None


def apply_tenant(cfg, tenant: dict | None):
    """Return a per-call effective Settings with this tenant's overrides applied
    (falls back to the global value for anything the tenant doesn't set). The
    rest of the call (roster/access/notify/guard) then transparently uses it."""
    if not tenant:
        return cfg
    updates = {
        k: tenant[k] for k in _OVERRIDE_KEYS
        if k in tenant and tenant[k] is not None
    }
    return cfg.model_copy(update=updates) if updates else cfg
