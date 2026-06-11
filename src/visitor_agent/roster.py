"""Company-roster fuzzy matching.

The park gives us a list of the companies inside it. When the LLM records a
来访单位 (which STT may have mangled — "蓝色金鱼" for "蓝色鲸鱼"), we snap it to the
closest official name on the roster. Matching combines a Hanzi similarity ratio
with a pinyin ratio (homophones like 金鱼/鲸鱼 are near-identical in pinyin), so
mis-heard company names get corrected and confirmed instead of stored wrong.

Disabled unless ROSTER_PATH points at a JSON file — so the base demo is
unaffected until a roster is provided.
"""

from __future__ import annotations

import difflib
import json
import os


def load_roster(path: str | None) -> list[tuple[str, str]]:
    """Return [(candidate, official_name)] pairs.

    The file is a JSON list of either strings, or objects
    {"name": "蓝色鲸鱼科技", "aliases": ["蓝色鲸鱼", "鲸鱼科技"]}.
    """
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    pairs: list[tuple[str, str]] = []
    for item in data:
        if isinstance(item, str):
            pairs.append((item, item))
        elif isinstance(item, dict) and item.get("name"):
            official = item["name"]
            pairs.append((official, official))
            for alias in item.get("aliases", []) or []:
                pairs.append((alias, official))
    return pairs


def _pinyin(s: str) -> str | None:
    try:
        from pypinyin import lazy_pinyin

        return "".join(lazy_pinyin(s))
    except Exception:  # noqa: BLE001 — pypinyin optional; fall back to Hanzi only
        return None


def _score(a: str, b: str) -> float:
    r = difflib.SequenceMatcher(None, a, b).ratio()
    pa, pb = _pinyin(a), _pinyin(b)
    if pa and pb:
        r = max(r, difflib.SequenceMatcher(None, pa, pb).ratio())
    return r


def match_company(
    text: str | None, roster: list[tuple[str, str]], threshold: float = 0.55
) -> tuple[str | None, float]:
    """Return (official_name, score) for the best match ≥ threshold, else (None, score)."""
    if not text or not roster:
        return (None, 0.0)
    text = text.strip()
    best_name: str | None = None
    best_score = 0.0
    for candidate, official in roster:
        if text == candidate:
            return (official, 1.0)
        if text in candidate or candidate in text:
            s = max(0.8, _score(text, candidate))
        else:
            s = _score(text, candidate)
        if s > best_score:
            best_name, best_score = official, s
    if best_score >= threshold:
        return (best_name, best_score)
    return (None, best_score)


def make_matcher(path: str | None, threshold: float = 0.55):
    """Build a callable(company_text) -> (official, score) or None if no roster."""
    roster = load_roster(path)
    if not roster:
        return None

    def _match(text: str | None) -> tuple[str | None, float]:
        return match_company(text, roster, threshold)

    return _match
