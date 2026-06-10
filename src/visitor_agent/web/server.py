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


@app.get("/api/profiles")
def api_profiles(min_visits: int = 1) -> JSONResponse:
    return JSONResponse(repo.visitor_profiles(limit=50, min_visits=min_visits))


@app.get("/admin", response_class=HTMLResponse)
def admin() -> HTMLResponse:
    return HTMLResponse(_ADMIN_HTML)


@app.post("/api/confirm/{visit_id}")
def api_confirm(visit_id: int) -> JSONResponse:
    """Local guard console: confirm + open gate from the Dashboard button."""
    visit = repo.mark_confirmed_by_id(visit_id)
    if visit is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    gate.open_gate(visit_id=visit.id, plate=visit.plate)
    call_id = f"visit-{visit.id}"
    repo.log_event(call_id, "confirmed", text=f"保安已确认放行 {visit.plate or ''}")
    repo.log_event(call_id, "gate", text="已发送抬杆指令 (gate open)")
    return JSONResponse(visit.to_dict())


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


# ----- browser voice client (talk to the agent with a mic, no phone) -----

@app.get("/token")
def mint_token(room: str = "voice-demo", identity: str = "visitor") -> JSONResponse:
    """Mint a LiveKit join token so the browser can join the agent's room."""
    from livekit import api

    cfg = get_settings()
    if not (cfg.livekit_api_key and cfg.livekit_api_secret and cfg.livekit_url):
        return JSONResponse({"error": "LiveKit not configured in .env"}, status_code=400)
    token = (
        api.AccessToken(cfg.livekit_api_key, cfg.livekit_api_secret)
        .with_identity(identity)
        .with_name(identity)
        .with_grants(api.VideoGrants(room_join=True, room=room))
        .to_jwt()
    )
    return JSONResponse({"url": cfg.livekit_url, "token": token, "room": room})


@app.get("/voice", response_class=HTMLResponse)
def voice() -> HTMLResponse:
    return HTMLResponse(_VOICE_HTML)


@app.get("/qr", response_class=HTMLResponse)
def qr() -> HTMLResponse:
    """A printable QR code that points visitors straight at the voice page —
    "扫码即用": stick it at the entrance, the visitor scans and talks."""
    base = get_settings().public_base_url.rstrip("/")
    target = f"{base}/voice"
    html = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>扫码登记</title>
<script src="https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js"></script>
<style>body{{font-family:-apple-system,Segoe UI,'PingFang SC',sans-serif;background:#f4f1ea;
text-align:center;padding-top:8vh}}#qr{{display:inline-block;background:#fff;padding:24px;border-radius:20px;
box-shadow:0 10px 40px rgba(0,0,0,.08)}}h1{{font-size:20px}}p{{color:#777}}a{{color:#c9742e;word-break:break-all}}</style>
</head><body><h1>🐳 扫码登记访客</h1><p>访客用手机扫码即可和 AI 门卫对话，无需电话</p>
<div id="qr"></div><p><a href="{target}">{target}</a></p>
<script>new QRCode(document.getElementById('qr'),{{text:"{target}",width:240,height:240}});</script>
</body></html>"""
    return HTMLResponse(html)


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
  .go{border:0;border-radius:999px;background:#39b54a;color:#fff;padding:5px 12px;cursor:pointer;font-size:12px}
</style></head><body>
<header><span class="dot"></span><h1>🐳 门卫控制台 · 实时</h1>
<span style="color:var(--muted);font-size:13px">拨打电话后，这里实时显示对话、采集字段、推送与放行</span></header>
<div class="wrap">
  <div class="panel"><h2>📞 实时通话时间线</h2>
    <div class="slots" id="slots"></div>
    <div id="feed"></div>
  </div>
  <div class="panel"><h2>🗂 访客记录 · 保安点"放行"即确认　<a href="/admin" target="_blank" style="font-size:12px">常客名单 →</a></h2>
    <table><thead><tr><th>车牌</th><th>单位</th><th>事由</th><th>登记</th><th>开闸时间</th><th>状态</th></tr></thead>
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
async function confirmVisit(id){try{await fetch('/api/confirm/'+id,{method:'POST'});visits();}catch(_){}}
async function visits(){try{const r=await fetch('/api/visits');const d=await r.json();
  document.getElementById('visits').innerHTML=d.map(v=>{
   const cell=v.status==='confirmed'
     ?'<span class="badge confirmedb">已放行</span>'
     :'<button class="go" onclick="confirmVisit('+v.id+')">✅ 放行</button>';
   const gate=v.confirmed_at?v.confirmed_at.slice(11,19)+' UTC':'—';
   return '<tr><td>'+(v.plate||'—')+'</td><td>'+(v.company||'—')+'</td><td>'+(v.reason||'—')+
     '</td><td>'+(v.entry_time||'—')+'</td><td>'+gate+'</td><td>'+cell+'</td></tr>';}).join('');}catch(_){}}
visits();setInterval(visits,3000);
</script></body></html>"""


_VOICE_HTML = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>和 AI 门卫对话 · Voice Agent</title>
<script src="https://cdn.jsdelivr.net/npm/livekit-client/dist/livekit-client.umd.min.js"></script>
<style>
  body{margin:0;font-family:-apple-system,Segoe UI,Roboto,'PingFang SC',sans-serif;background:#f4f1ea;
    color:#2b2b2b;display:flex;min-height:100vh;align-items:center;justify-content:center}
  .card{background:#fff;border-radius:20px;box-shadow:0 10px 40px rgba(0,0,0,.08);padding:36px 40px;
    text-align:center;max-width:420px;width:90%}
  h1{font-size:20px;margin:0 0 6px} p{color:#777;margin:6px 0 20px;line-height:1.6;font-size:14px}
  button{font-size:16px;padding:14px 28px;border:0;border-radius:999px;background:#c9742e;color:#fff;
    cursor:pointer;box-shadow:0 6px 16px rgba(201,116,46,.35)} button:disabled{opacity:.5;cursor:default}
  .status{margin-top:18px;font-size:14px;color:#555;min-height:22px}
  .mic{width:64px;height:64px;border-radius:50%;background:#39b54a;margin:0 auto 16px;display:none;
    box-shadow:0 0 0 0 rgba(57,181,74,.6);animation:p 1.5s infinite} @keyframes p{to{box-shadow:0 0 0 16px rgba(57,181,74,0)}}
  a{color:#c9742e}
</style></head><body>
<div class="card">
  <div class="mic" id="mic"></div>
  <h1>🐳 和 AI 门卫对话</h1>
  <p>点下面按钮、允许麦克风权限，就能直接对着电脑说话登记——无需电话。<br>
     说完打开 <a href="/dashboard" target="_blank">后台 Dashboard</a> 看实时效果。</p>
  <button id="btn">📞 接入门卫</button>
  <div class="status" id="status"></div>
</div>
<script>
const btn=document.getElementById('btn'),st=document.getElementById('status'),mic=document.getElementById('mic');
btn.onclick=async()=>{
  btn.disabled=true; st.textContent='正在接入…';
  try{
    const id='visitor-'+Math.random().toString(36).slice(2,8);
    const r=await fetch('/token?room=voice-demo&identity='+id);
    const d=await r.json(); if(d.error){throw new Error(d.error);}
    const room=new LivekitClient.Room();
    room.on(LivekitClient.RoomEvent.TrackSubscribed,(track)=>{
      if(track.kind==='audio'){const el=track.attach();el.autoplay=true;
        el.setAttribute('playsinline','');el.muted=false;document.body.appendChild(el);
        el.play&&el.play().catch(()=>{});}});
    room.on(LivekitClient.RoomEvent.Disconnected,()=>{st.textContent='已挂断';mic.style.display='none';btn.disabled=false;});
    await room.connect(d.url,d.token);
    await room.localParticipant.setMicrophoneEnabled(true);
    mic.style.display='block';
    st.innerHTML='✅ 已接入，门卫会先开口——请直接说话。<br>（说完可关闭页面挂断）';
  }catch(e){st.textContent='接入失败：'+e.message+'（确认 .env 里 LiveKit 配置 + agent worker 已启动）';btn.disabled=false;}
};
</script></body></html>"""


_ADMIN_HTML = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>常客名单 · 访客画像</title>
<style>
  body{font-family:-apple-system,Segoe UI,'PingFang SC',sans-serif;background:#f4f1ea;color:#2b2b2b;margin:0}
  header{padding:16px 24px;display:flex;align-items:center;gap:10px}
  header h1{font-size:18px;margin:0} a{color:#c9742e}
  .panel{background:#fff;border-radius:16px;box-shadow:0 6px 24px rgba(0,0,0,.06);margin:0 24px 24px;padding:16px;overflow:auto}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #eee;white-space:nowrap}
  th{color:#777;font-weight:600} .num{font-weight:700;color:#c9742e}
  .chip{background:#f6f3ec;border-radius:999px;padding:2px 8px;margin:1px;display:inline-block;font-size:12px}
</style></head><body>
<header><h1>🏆 常客名单 / 访客画像</h1>
<span style="color:#777;font-size:13px">按人聚合（手机号=人，车牌=车）·来访越多越靠前</span>
<a href="/dashboard" style="margin-left:auto">← 返回实时后台</a></header>
<div class="panel"><table>
<thead><tr><th>称呼</th><th>手机号</th><th>车牌</th><th>来访次数</th><th>已放行</th><th>常去单位</th><th>最近一次</th></tr></thead>
<tbody id="rows"></tbody></table></div>
<script>
async function load(){try{const r=await fetch('/api/profiles');const d=await r.json();
  document.getElementById('rows').innerHTML=d.map(p=>'<tr>'+
   '<td>'+(p.name||'—')+'</td>'+
   '<td>'+(p.phone||'—')+'</td>'+
   '<td>'+(p.plates&&p.plates.length?p.plates.map(x=>'<span class=chip>'+x+'</span>').join(''):'—')+'</td>'+
   '<td class=num>'+p.visit_count+'</td>'+
   '<td>'+p.confirmed_count+'</td>'+
   '<td>'+(p.companies&&p.companies.length?p.companies.map(x=>'<span class=chip>'+x+'</span>').join(''):'—')+'</td>'+
   '<td>'+(p.last_company||'—')+'／'+(p.last_reason||'—')+'　'+(p.last_time||'')+'</td>'+
   '</tr>').join('')||'<tr><td colspan=7 style="color:#999">暂无数据，先登记几位访客</td></tr>';}catch(_){}}
load();setInterval(load,4000);
</script></body></html>"""


def main() -> None:
    import uvicorn
    from dotenv import load_dotenv

    load_dotenv()  # make .env values (DB, notify, Hikvision, LiveKit) visible
    get_settings.cache_clear()
    cfg = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=cfg.web_port)


if __name__ == "__main__":
    main()
