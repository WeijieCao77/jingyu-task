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

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
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
        call_id = f"visit-{confirmed.id}"
        repo.log_event(call_id, "confirmed", text=f"保安已确认放行 {confirmed.plate or ''}")
        repo.log_event(call_id, "gate", text="已发送抬杆指令 (gate open)")

    v = (confirmed or visit)
    detail = (
        f"车牌 <b>{v.plate or '—'}</b>　{v.company or '—'}　{v.reason or '—'}<br>"
        f"入场时间 {v.entry_time or '—'}"
    )
    head = "已放行 ✓" if not already else "已确认（重复点击）"
    return _page(head, detail + "<br><br>抬杆指令已发送。")


# ----- live dashboard -----

@app.get("/api/visits")
def api_visits() -> JSONResponse:
    return JSONResponse([v.to_dict() for v in repo.recent_visits(limit=30)])


@app.get("/events/stream")
async def events_stream() -> StreamingResponse:
    """Server-Sent Events: stream new call-timeline events as they land."""

    async def gen():
        # Start a little behind so the operator sees recent context on load.
        last = max(0, repo.latest_event_id() - 40)
        yield "retry: 2000\n\n"
        while True:
            try:
                rows = repo.events_after(last, limit=200)
            except Exception:  # noqa: BLE001
                rows = []
            for ev in rows:
                last = ev.id
                yield f"data: {json.dumps(ev.to_dict(), ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.7)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    return HTMLResponse(_DASHBOARD_HTML)


@app.get("/", response_class=HTMLResponse)
def root() -> HTMLResponse:
    return HTMLResponse(_DASHBOARD_HTML)


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


_DASHBOARD_HTML = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>门卫控制台 · Visitor Agent</title>
<style>
  :root{--cream:#f4f1ea;--card:#fff;--ink:#2b2b2b;--muted:#777;--accent:#c9742e}
  *{box-sizing:border-box} body{margin:0;font-family:-apple-system,Segoe UI,Roboto,'PingFang SC',sans-serif;
    background:var(--cream);color:var(--ink)}
  header{padding:16px 24px;display:flex;align-items:center;gap:12px}
  header h1{font-size:18px;margin:0} .dot{width:10px;height:10px;border-radius:50%;background:#39b54a;
    box-shadow:0 0 0 0 rgba(57,181,74,.6);animation:p 1.6s infinite} @keyframes p{to{box-shadow:0 0 0 10px rgba(57,181,74,0)}}
  .wrap{display:grid;grid-template-columns:1.4fr 1fr;gap:16px;padding:0 24px 24px}
  @media(max-width:820px){.wrap{grid-template-columns:1fr}}
  .panel{background:var(--card);border-radius:16px;box-shadow:0 6px 24px rgba(0,0,0,.06);padding:16px;min-height:200px}
  .panel h2{font-size:14px;color:var(--muted);margin:0 0 10px;text-transform:uppercase;letter-spacing:.05em}
  #feed{max-height:62vh;overflow:auto;display:flex;flex-direction:column;gap:8px}
  .ev{padding:8px 12px;border-radius:12px;line-height:1.5;animation:f .3s ease}
  @keyframes f{from{opacity:0;transform:translateY(6px)}} .ev .t{font-size:11px;color:var(--muted);margin-right:6px}
  .user{background:#eef4ff} .agent{background:#fff6ec;border:1px solid #f3e2cf}
  .slot{background:#f3f7ef;color:#3a6} .completed{background:#e8f7ec;font-weight:600}
  .pushed{background:#eaf6ff} .confirmed{background:#e9f9ea;font-weight:600} .gate{background:#fff0f0;color:#b23}
  .call_started{background:#f0eefc;font-weight:600}
  .slots{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px}
  .chip{background:#f6f3ec;border-radius:999px;padding:6px 12px;font-size:13px}
  .chip b{color:var(--accent)} table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{text-align:left;padding:6px 8px;border-bottom:1px solid #eee} .badge{font-size:11px;padding:2px 8px;border-radius:999px}
  .pending{background:#fff3e0;color:#b26a00} .confirmedb{background:#e8f7ec;color:#2e7d32}
</style></head><body>
<header><span class="dot"></span><h1>🐳 门卫控制台 · 实时</h1>
<span style="color:var(--muted);font-size:13px">拨打电话后，这里实时显示对话、采集字段、推送与放行</span></header>
<div class="wrap">
  <div class="panel"><h2>📞 实时通话时间线</h2>
    <div class="slots" id="slots"></div>
    <div id="feed"></div>
  </div>
  <div class="panel"><h2>🗂 访客记录</h2>
    <table><thead><tr><th>车牌</th><th>单位</th><th>事由</th><th>时间</th><th>状态</th></tr></thead>
    <tbody id="visits"></tbody></table>
  </div>
</div>
<script>
const F={user:'你 · 访客',agent:'AI 门卫',slot:'抽取',completed:'登记完成',
  pushed:'推送门卫',confirmed:'保安确认',gate:'抬杆',call_started:'来电'};
const feed=document.getElementById('feed'),slots=document.getElementById('slots');
function row(e){const d=document.createElement('div');d.className='ev '+e.kind;
  const t=(e.created_at||'').slice(11,19);
  d.innerHTML='<span class="t">'+t+'</span><b>'+(F[e.kind]||e.kind)+'</b> '+(e.text||'');
  feed.appendChild(d);feed.scrollTop=feed.scrollHeight;
  if(e.kind==='slot'&&e.payload){try{const p=JSON.parse(e.payload);
    slots.innerHTML=['plate','company','reason','phone'].map(k=>{
      const L={plate:'车牌',company:'单位',reason:'事由',phone:'手机'}[k];
      return '<span class="chip">'+L+'：<b>'+(p[k]||'…')+'</b></span>';}).join('');}catch(_){}}
}
const es=new EventSource('/events/stream');es.onmessage=m=>{try{row(JSON.parse(m.data))}catch(_){}};
async function visits(){try{const r=await fetch('/api/visits');const d=await r.json();
  document.getElementById('visits').innerHTML=d.map(v=>'<tr><td>'+(v.plate||'—')+'</td><td>'+
   (v.company||'—')+'</td><td>'+(v.reason||'—')+'</td><td>'+(v.entry_time||'—')+'</td><td>'+
   '<span class="badge '+(v.status==='confirmed'?'confirmedb':'pending')+'">'+
   (v.status==='confirmed'?'已放行':'待确认')+'</span></td></tr>').join('');}catch(_){}}
visits();setInterval(visits,3000);
</script></body></html>"""


def main() -> None:
    import uvicorn

    cfg = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=cfg.web_port)


if __name__ == "__main__":
    main()
