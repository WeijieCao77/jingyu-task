"""Blacklist / whitelist access control for plates and phones.

The park can pre-classify vehicles/people:
  - **blacklist** — banned (e.g. unpaid fees, prior incident): alert the guard
    loudly, never auto-open the gate.
  - **whitelist** — pre-approved regulars / VIP: flag for fast approval, and
    optionally auto-pass (AUTO_PASS_WHITELIST).

Matching is a *deterministic exact match* on the normalized plate or phone —
unlike company roster matching, an access decision must be precise, so there is
no fuzzy guessing here. If something is on both lists, the blacklist wins
(fail-safe). The same `normalize_plate` / `normalize_phone` used everywhere else
is applied to both the list and the live value, so "粤A 123 45" matches "粤A12345".

Disabled unless ACCESS_LIST_PATH points at a JSON file, so the base demo is
unaffected until a list is provided.
"""

from __future__ import annotations

import json
import os

from .slots import normalize_phone, normalize_plate

# blacklist is checked first so it takes precedence over a whitelist hit.
_STATUSES = ("blacklist", "whitelist")


def load_access_list(path: str | None) -> dict[str, list[dict]]:
    """Load + normalize the access list.

    File format:
        {
          "blacklist": [{"plate": "沪A00000", "phone": "13900000000",
                         "name": "...", "reason": "欠费未结"}],
          "whitelist": [{"plate": "沪A12345", "name": "张师傅",
                         "reason": "长期合作"}]
        }
    Each entry needs at least a plate or a phone. Returns
    {"blacklist": [...], "whitelist": [...]} with normalized plate/phone.
    """
    empty: dict[str, list[dict]] = {"blacklist": [], "whitelist": []}
    if not path or not os.path.exists(path):
        return empty
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    out: dict[str, list[dict]] = {"blacklist": [], "whitelist": []}
    for status in _STATUSES:
        for item in data.get(status, []) or []:
            plate = normalize_plate(item.get("plate"))
            phone = normalize_phone(item.get("phone"))
            if not (plate or phone):
                continue  # nothing to match on
            out[status].append(
                {"plate": plate, "phone": phone,
                 "name": item.get("name"), "reason": item.get("reason")}
            )
    return out


def check_access(
    plate: str | None, phone: str | None, access: dict[str, list[dict]]
) -> dict | None:
    """Return {"status","matched_on","name","reason"} for the first match, else
    None. Blacklist is checked before whitelist (precedence / fail-safe)."""
    np, nph = normalize_plate(plate), normalize_phone(phone)
    for status in _STATUSES:
        for e in access.get(status, []):
            if e["plate"] and e["plate"] == np:
                return {"status": status, "matched_on": "plate",
                        "name": e["name"], "reason": e["reason"]}
            if e["phone"] and e["phone"] == nph:
                return {"status": status, "matched_on": "phone",
                        "name": e["name"], "reason": e["reason"]}
    return None


def make_access_checker(path: str | None):
    """Build a callable(plate, phone) -> dict|None, or None if no list is set."""
    access = load_access_list(path)
    if not access["blacklist"] and not access["whitelist"]:
        return None

    def _check(plate: str | None, phone: str | None) -> dict | None:
        return check_access(plate, phone, access)

    return _check
