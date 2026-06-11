"""The structured information the agent must collect, plus light normalization.

This is the heart of "what the call is for": four caller-supplied fields
(plate, company, reason, phone) and an auto-stamped entry time. Keeping this in
one small, dependency-free module lets both the live LiveKit agent and the
offline simulator share identical slot logic, and lets the unit tests exercise
it without any network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

# Required fields, in the order a guard would naturally read them back.
REQUIRED_FIELDS = ("plate", "company", "reason", "phone")

FIELD_LABELS_ZH = {
    "plate": "车牌号",
    "company": "来访单位",
    "reason": "来访事由",
    "phone": "手机号",
}

# Chinese mainland plate: province char + letter + 5-6 alnum (incl. new-energy 6).
_PLATE_RE = re.compile(r"[一-龥][A-Z][A-Z0-9]{5,6}", re.IGNORECASE)
_PHONE_RE = re.compile(r"1[3-9]\d{9}")

# Spoken province names → plate character. STT often returns the full province
# name ("广东A12345") instead of the abbreviation; snap it deterministically.
_PROVINCE_NAME_TO_CHAR = {
    "北京": "京", "天津": "津", "上海": "沪", "重庆": "渝", "河北": "冀",
    "山西": "晋", "内蒙古": "蒙", "辽宁": "辽", "吉林": "吉", "黑龙江": "黑",
    "江苏": "苏", "浙江": "浙", "安徽": "皖", "福建": "闽", "江西": "赣",
    "山东": "鲁", "河南": "豫", "湖北": "鄂", "湖南": "湘", "广东": "粤",
    "广西": "桂", "海南": "琼", "四川": "川", "贵州": "贵", "云南": "云",
    "西藏": "藏", "陕西": "陕", "甘肃": "甘", "青海": "青", "宁夏": "宁",
    "新疆": "新",
}


def normalize_plate(value: str | None) -> str | None:
    """Uppercase letters, strip spaces/dots; map spoken province name → char."""
    if not value:
        return None
    cleaned = re.sub(r"[\s\.\-·•‧・]", "", value).upper()
    # Replace a leading spoken province name with its plate character.
    for name, char in _PROVINCE_NAME_TO_CHAR.items():
        if cleaned.startswith(name):
            cleaned = char + cleaned[len(name):]
            break
    m = _PLATE_RE.search(cleaned)
    return m.group(0) if m else (cleaned or None)


def normalize_phone(value: str | None) -> str | None:
    """Keep digits only; surface a clean 11-digit mainland mobile if present."""
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    m = _PHONE_RE.search(digits)
    return m.group(0) if m else (digits or None)


@dataclass
class VisitorInfo:
    """Mutable slot state for a single call."""

    plate: str | None = None
    company: str | None = None
    reason: str | None = None
    phone: str | None = None
    name: str | None = None          # optional — for 张师傅 personalization
    entry_time: str | None = None
    extra: dict = field(default_factory=dict)

    def update(
        self,
        plate: str | None = None,
        company: str | None = None,
        reason: str | None = None,
        phone: str | None = None,
        name: str | None = None,
    ) -> None:
        """Apply a partial update; only non-empty values overwrite."""
        if plate:
            self.plate = normalize_plate(plate)
        if company:
            self.company = company.strip()
        if reason:
            self.reason = reason.strip()
        if phone:
            self.phone = normalize_phone(phone)
        if name:
            self.name = name.strip()

    def missing_fields(self) -> list[str]:
        return [f for f in REQUIRED_FIELDS if not getattr(self, f)]

    def is_complete(self) -> bool:
        return not self.missing_fields()

    def stamp_entry_time(self, tz: str = "Asia/Shanghai") -> str:
        self.entry_time = datetime.now(ZoneInfo(tz)).strftime("%Y-%m-%d %H:%M")
        return self.entry_time

    def human_summary(self) -> str:
        """Short, natural read-back used in the agent's confirmation line."""
        parts = []
        if self.plate:
            parts.append(self.plate)
        if self.company:
            parts.append(self.company)
        if self.reason:
            parts.append(self.reason)
        return "，".join(parts)

    def missing_labels_zh(self) -> list[str]:
        return [FIELD_LABELS_ZH[f] for f in self.missing_fields()]

    def to_dict(self) -> dict:
        return {
            "plate": self.plate,
            "company": self.company,
            "reason": self.reason,
            "phone": self.phone,
            "name": self.name,
            "entry_time": self.entry_time,
        }
