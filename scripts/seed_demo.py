"""Seed reproducible demo data into the visits DB.

Idempotent: clears the `visits` table, then inserts a fixed demo set covering
frequent visitors (常客回访), several园区 companies, mixed status, whitelist/
blacklist flags, and timestamps spread across today / this week / this month so
the guard data-query features (count/list/busiest-hours/frequent-visitors) all
have something real to return.

Run it where DATABASE_URL points at the target DB (e.g. inside the Railway
container: `python scripts/seed_demo.py`). Uses Asia/Shanghai (UTC+8) for the
human-facing entry_time strings.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

# Allow running from the repo root (src layout) as well as the container
# (PYTHONPATH=/app/src already set).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlalchemy.orm import Session  # noqa: E402

from visitor_agent.db import repo  # noqa: E402
from visitor_agent.db.models import Visit  # noqa: E402

OFFSET = timedelta(hours=8)  # Asia/Shanghai, no DST
_now_utc = datetime.now(timezone.utc)
_local_now = _now_utc + OFFSET


def when(days_ago: int, hh: int, mm: int):
    """Return (created_at UTC tz-aware, entry_time local 'YYYY-MM-DD HH:MM')."""
    d = (_local_now - timedelta(days=days_ago)).date()
    local_dt = datetime(d.year, d.month, d.day, hh, mm)
    created = (local_dt - OFFSET).replace(tzinfo=timezone.utc)
    return created, local_dt.strftime("%Y-%m-%d %H:%M")


# (name, phone, plate, company, reason, access_status, [(days_ago, hh, mm, status), ...])
PEOPLE = [
    ("张师傅", "13800138001", "沪A12345", "蓝色鲸鱼科技", "送货", "whitelist",
     [(0, 9, 15, "confirmed"), (2, 10, 30, "confirmed"), (6, 14, 20, "confirmed"),
      (13, 9, 45, "confirmed"), (22, 15, 10, "confirmed")]),
    ("赵师傅", "13611112222", "沪C66666", "顺丰速运", "取派件", "whitelist",
     [(0, 11, 5, "confirmed"), (1, 16, 40, "confirmed"), (8, 10, 15, "confirmed"),
      (20, 14, 50, "confirmed")]),
    ("李经理", "13800138000", "苏E20000", "远景智能", "商务洽谈", "whitelist",
     [(0, 14, 30, "pending"), (4, 15, 20, "confirmed"), (18, 10, 50, "confirmed")]),
    ("王总", "13700137000", "粤B88888", "宁德时代", "项目考察", "whitelist",
     [(3, 9, 30, "confirmed"), (16, 11, 20, "confirmed")]),
    ("孙女士", "13522223333", "沪D77777", "京东物流", "送货", None,
     [(0, 10, 5, "confirmed"), (9, 15, 35, "confirmed")]),
    ("周工", "13433334444", "浙A55555", "大疆创新", "技术对接", None,
     [(5, 14, 10, "confirmed")]),
    ("陈先生", "13344445555", "京A33333", "商汤科技", "面试", None,
     [(0, 9, 50, "confirmed")]),
    ("吴女士", "13255556666", "沪B22222", "海康威视", "参观", None,
     [(2, 16, 15, "confirmed")]),
    ("郑工", "13166667777", "津A99999", "字节跳动", "商务拜访", None,
     [(11, 11, 45, "confirmed")]),
    ("推销人员", "13900000000", "沪A00000", None, "上门推销", "blacklist",
     [(1, 13, 0, "pending")]),
]


def build_rows():
    rows = []
    i = 0
    for name, phone, plate, company, reason, access, visits in PEOPLE:
        for (days_ago, hh, mm, status) in visits:
            created, entry = when(days_ago, hh, mm)
            i += 1
            rows.append(Visit(
                plate=plate, company=company, reason=reason, phone=phone, name=name,
                entry_time=entry, status=status, access_status=access,
                created_at=created,
                confirmed_at=created if status == "confirmed" else None,
                confirm_token=f"seed-{i:03d}",
            ))
    return rows


def main():
    # Default: use DATABASE_URL from config (inside the container this is the
    # Postgres reference). Override with SEED_DATABASE_URL to seed a remote DB
    # over its public proxy URL from elsewhere.
    eng = repo.init_db(os.environ.get("SEED_DATABASE_URL") or None)
    rows = build_rows()
    with Session(eng) as s:
        before = s.query(Visit).count()
        s.query(Visit).delete()
        s.commit()
        s.add_all(rows)
        s.commit()
        after = s.query(Visit).count()
    print(f"seed_demo: cleared {before} old visit(s), inserted {len(rows)}, now {after}.")


if __name__ == "__main__":
    main()
