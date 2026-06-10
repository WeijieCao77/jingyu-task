"""Confirm web server.

Two responsibilities:
  1. GET /confirm?token=...  — the link the guard taps inside WeCom. Validates
     the token, flips the visit to confirmed, fires the gate stub, returns a
     small HTML page.
  2. POST /guard/query       — natural-language guard query agent (bonus).

Run:  python -m visitor_agent.web.server
      (or: uvicorn visitor_agent.web.server:app --port 8080)
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from ..config import get_settings
from ..db import repo
from ..notify import gate


@asynccontextmanager
async def _lifespan(app: FastAPI):
    repo.init_db(get_settings().database_url)
    yield


app = FastAPI(title="Visitor Agent — Confirm & Query", lifespan=_lifespan)


def _page(title: str, body: str, color: str = "#2e7d32") -> HTMLResponse:
    html = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title></head>
<body style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;
background:#f4f1ea;display:flex;min-height:100vh;align-items:center;
justify-content:center;margin:0">
<div style="background:#fff;border-radius:16px;padding:32px 40px;
box-shadow:0 8px 30px rgba(0,0,0,.08);text-align:center;max-width:360px">
<div style="font-size:48px;color:{color}">●</div>
<h2 style="margin:8px 0 4px">{title}</h2>
<div style="color:#555;line-height:1.6">{body}</div>
</div></body></html>"""
    return HTMLResponse(html)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/confirm", response_class=HTMLResponse)
def confirm(token: str = Query(...)) -> HTMLResponse:
    visit = repo.get_visit_by_token(token)
    if visit is None:
        return _page("链接无效", "未找到对应的访客记录。", color="#c62828")

    already = visit.status == "confirmed"
    confirmed = repo.mark_confirmed(token)
    if confirmed and not already:
        gate.open_gate(visit_id=confirmed.id, plate=confirmed.plate)

    v = (confirmed or visit)
    detail = (
        f"车牌 <b>{v.plate or '—'}</b>　{v.company or '—'}　{v.reason or '—'}<br>"
        f"入场时间 {v.entry_time or '—'}"
    )
    head = "已放行 ✓" if not already else "已确认（重复点击）"
    return _page(head, detail + "<br><br>抬杆指令已发送。")


# ----- bonus: guard query agent over the API -----

class GuardQuery(BaseModel):
    question: str


@app.post("/guard/query")
def guard_query(q: GuardQuery) -> JSONResponse:
    from ..guard_query import answer_question

    try:
        answer = answer_question(q.question)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": str(exc)}, status_code=500)
    return JSONResponse({"question": q.question, "answer": answer})


def main() -> None:
    import uvicorn

    cfg = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=cfg.web_port)


if __name__ == "__main__":
    main()
