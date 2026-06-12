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


def _notify_room_approved(room: str | None) -> None:
    """Best-effort: tell the visitor's live call the gate was approved, so the
    AI can announce it (FR-2). No-op if LiveKit isn't configured/installed or the
    visitor already hung up — must never break the confirm/gate flow."""
    if not room:
        return
    cfg = get_settings()
    if not (cfg.livekit_url and cfg.livekit_api_key and cfg.livekit_api_secret):
        return
    try:
        import asyncio

        from livekit import api

        host = cfg.livekit_url.replace("wss://", "https://").replace("ws://", "http://")

        async def _send() -> None:
            lkapi = api.LiveKitAPI(host, cfg.livekit_api_key, cfg.livekit_api_secret)
            try:
                await lkapi.room.send_data(
                    api.SendDataRequest(
                        room=room,
                        data=json.dumps({"type": "approved"}).encode("utf-8"),
                        kind=api.DataPacketKind.KIND_RELIABLE,
                        topic="gate",
                    )
                )
            finally:
                await lkapi.aclose()

        # Bounded so a slow/unreachable LiveKit can't delay the guard's confirm.
        asyncio.run(asyncio.wait_for(_send(), timeout=3.0))
    except Exception:  # noqa: BLE001 — visitor may have hung up; never break confirm
        pass


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/confirm", response_class=HTMLResponse)
def confirm(token: str = Query(...)) -> HTMLResponse:
    visit = repo.get_visit_by_token(token)
    if visit is None:
        return _page("链接无效", "未找到对应的访客记录。", color="#c62828")

    # Blacklist: registered but NOT released (园区策略：黑名单登记不放行). The gate
    # never opens from the normal flow; a human must handle it out-of-band.
    if visit.access_status == "blacklist":
        return _page(
            "⛔ 黑名单 · 禁止放行",
            f"车牌 <b>{visit.plate or '—'}</b> 在黑名单，已登记但<b>不予放行</b>。请人工核实处理。",
            color="#c62828",
        )

    already = visit.status == "confirmed"
    confirmed = repo.mark_confirmed(token)
    if confirmed and not already:
        gate.open_gate(visit_id=confirmed.id, plate=confirmed.plate)
        call_id = f"visit-{confirmed.id}"
        repo.log_event(call_id, "confirmed", text=f"保安已确认放行 {confirmed.plate or ''}")
        repo.log_event(call_id, "gate", text="已发送抬杆指令 (gate open)")
        _notify_room_approved(confirmed.room)  # AI tells the visitor (FR-2)

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


def _range_window(range_: str):
    """Map today|week|month|all → (since, until) in the configured timezone."""
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(get_settings().timezone)
    now = datetime.now(tz)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if range_ == "today":
        since = midnight
    elif range_ == "week":
        since = midnight - timedelta(days=now.weekday())
    elif range_ == "month":
        since = midnight.replace(day=1)
    else:
        return None, None
    return since.astimezone(timezone.utc), None


@app.get("/api/query")
def api_query(range: str = "all", company: str = "", status: str = "",
              plate: str = "", phone: str = "", limit: int = 50) -> JSONResponse:
    """Deterministic structured query (no LLM): count + matching list + hour
    histogram for the given filters. Powers the 'filter' mode of the data center."""
    since, until = _range_window(range)
    st = status or None
    visits = repo.query_visits(since=since, until=until, company=company or None,
                               plate=plate or None, phone=phone or None,
                               status=st, limit=limit)
    return JSONResponse({
        "count": repo.count_visits(since=since, until=until, company=company or None, status=st),
        "released": repo.count_visits(since=since, until=until, company=company or None, status="confirmed"),
        "visits": [v.to_dict() for v in visits],
        "by_hour": repo.visits_by_hour(since=since),
    })


@app.get("/admin", response_class=HTMLResponse)
def admin() -> HTMLResponse:
    return HTMLResponse(_ADMIN_HTML)


@app.post("/api/confirm/{visit_id}")
def api_confirm(visit_id: int) -> JSONResponse:
    """Local guard console: confirm + open gate from the Dashboard button."""
    visit = repo.get_visit_by_id(visit_id)
    if visit is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    if visit.access_status == "blacklist":  # 黑名单登记不放行
        return JSONResponse(
            {"error": "blacklisted", "message": "黑名单车辆，禁止放行"}, status_code=403
        )
    visit = repo.mark_confirmed_by_id(visit_id)
    gate.open_gate(visit_id=visit.id, plate=visit.plate)
    call_id = f"visit-{visit.id}"
    repo.log_event(call_id, "confirmed", text=f"保安已确认放行 {visit.plate or ''}")
    repo.log_event(call_id, "gate", text="已发送抬杆指令 (gate open)")
    _notify_room_approved(visit.room)  # AI tells the visitor (FR-2)
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
    cfg = get_settings()
    if not (cfg.livekit_api_key and cfg.livekit_api_secret and cfg.livekit_url):
        # Report "not configured" without needing the livekit package installed.
        return JSONResponse({"error": "LiveKit not configured in .env"}, status_code=400)

    from livekit import api

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


@app.get("/guard_call", response_class=HTMLResponse)
def guard_call() -> HTMLResponse:
    """Guard joins a visitor's live room to take over the conversation (转人工)."""
    return HTMLResponse(_GUARD_CALL_HTML)


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
    history: list[dict] | None = None  # prior [{role, content}] turns → follow-ups


@app.post("/guard/query")
def guard_query(q: GuardQuery) -> JSONResponse:
    from ..guard_query import answer_question

    try:
        answer = answer_question(q.question, history=q.history)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": str(exc)}, status_code=500)
    return JSONResponse({"question": q.question, "answer": answer})


@app.get("/ask", response_class=HTMLResponse)
def ask() -> HTMLResponse:
    """Guard data-query page: 保安自然语言问数据（本月多少车放行、找哪家多少人、高峰时段…）。"""
    return HTMLResponse(_ASK_HTML)


_DASHBOARD_HTML = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>门卫控制台</title>
<style>
  :root{--bg:#eef1f6;--card:#fff;--ink:#1f2733;--muted:#8a94a6;--line:#eceff4;
        --green:#1ea672;--greenbg:#e7f6ef;--amber:#c77b1a;--amberbg:#fdf3e3}
  *{box-sizing:border-box} body{margin:0;font-family:-apple-system,'Segoe UI',Roboto,'PingFang SC',sans-serif;
    background:var(--bg);color:var(--ink)}
  header{padding:18px 28px;display:flex;align-items:center;gap:12px}
  header h1{font-size:20px;margin:0;font-weight:700;letter-spacing:.5px}
  header .sub{color:var(--muted);font-size:13px}
  header a{margin-left:auto;color:#566;text-decoration:none;font-size:14px;
    background:#fff;padding:8px 14px;border-radius:999px;box-shadow:0 2px 8px rgba(0,0,0,.05)}
  .live{width:9px;height:9px;border-radius:50%;background:var(--green);
    box-shadow:0 0 0 0 rgba(30,166,114,.5);animation:p 1.8s infinite}
  @keyframes p{to{box-shadow:0 0 0 9px rgba(30,166,114,0)}}
  .wrap{padding:0 28px 32px;max-width:1100px}
  #alerts{display:flex;flex-direction:column;gap:10px;margin-bottom:16px}
  .alert{background:var(--amberbg);border:1px solid #f0d8a8;color:#8a5a12;border-radius:14px;
    padding:12px 16px;display:flex;align-items:center;gap:12px;animation:f .3s ease}
  @keyframes f{from{opacity:0;transform:translateY(-4px)}}
  .alert .join{margin-left:auto;background:var(--amber);color:#fff;border:0;border-radius:999px;
    padding:8px 16px;font-size:14px;cursor:pointer;text-decoration:none}
  .card{background:var(--card);border-radius:18px;box-shadow:0 8px 30px rgba(20,30,50,.06);overflow:hidden}
  .card h2{font-size:15px;margin:0;padding:18px 22px;border-bottom:1px solid var(--line);
    display:flex;align-items:center;gap:8px}
  table{width:100%;border-collapse:collapse;font-size:14px}
  th{text-align:left;color:var(--muted);font-weight:600;font-size:12px;padding:12px 16px;background:#fafbfd}
  td{padding:14px 16px;border-top:1px solid var(--line);vertical-align:middle}
  tr.new td{animation:hl 2s ease}
  @keyframes hl{from{background:#fff7e9}}
  .plate{font-weight:700;font-variant-numeric:tabular-nums}
  .pill{font-size:12px;padding:4px 12px;border-radius:999px;font-weight:600}
  .pill.ok{background:var(--greenbg);color:var(--green)}
  .pill.wait{background:var(--amberbg);color:var(--amber)}
  .pill.bad{background:#fdecec;color:#c62828}
  .pill.vip{background:var(--greenbg);color:var(--green)}
  .go{border:0;border-radius:10px;background:var(--green);color:#fff;padding:9px 18px;
    font-size:14px;font-weight:600;cursor:pointer;box-shadow:0 3px 10px rgba(30,166,114,.3)}
  .go:active{transform:translateY(1px)}
  .empty{padding:40px;text-align:center;color:var(--muted)}
  .muted{color:var(--muted)}
</style></head><body>
<header><span class="live"></span><h1>🐳 门卫控制台</h1>
<span class="sub">收到访客信息 → 核对 → 一键放行</span>
<a href="/ask" target="_blank" style="margin-left:auto">🔎 数据查询</a>
<a href="/admin" target="_blank" style="margin-left:8px">🏆 常客名单</a></header>
<div class="wrap">
  <div id="alerts"></div>
  <div class="card">
    <h2>🗂 访客登记</h2>
    <table><thead><tr><th>车牌</th><th>来访单位</th><th>事由</th><th>手机</th><th>姓名</th>
      <th>登记时间</th><th>状态</th><th></th></tr></thead>
      <tbody id="visits"></tbody></table>
    <div class="empty" id="empty" style="display:none">暂无访客记录</div>
  </div>
</div>
<script>
// Guard view = info table + buttons only. Full transcript stays in the DB; the
// only live events surfaced here are the ones a guard must act on: an incoming
// call (proactive takeover) and a transfer-to-human request.
const alerts={}; // call_id -> element
function renderAlert(e){
  if(e.kind==='human_joined'){const el=alerts[e.call_id]; if(el){el.remove();delete alerts[e.call_id];} return;}
  if(e.kind!=='call_started'&&e.kind!=='escalation')return;
  let el=alerts[e.call_id];
  if(!el){el=document.createElement('div');el.className='alert';alerts[e.call_id]=el;
    document.getElementById('alerts').appendChild(el);}
  const esc=e.kind==='escalation';
  el.style.background=esc?'#fdecec':'';el.style.borderColor=esc?'#f3c0c0':'';
  el.innerHTML=(esc?'⚠️ <b>访客请求转人工</b>　':'📞 <b>有访客来电</b>　')+
    '<span class="muted">'+(e.text||'')+'</span>'+
    '<a class="join" href="/guard_call?room='+encodeURIComponent(e.call_id)+'" target="_blank">'+
    (esc?'立即介入':'介入通话')+'</a>';
}
try{const es=new EventSource('/events/stream');
  es.onmessage=m=>{try{renderAlert(JSON.parse(m.data))}catch(_){}};}catch(_){}

let seen=new Set();
async function confirmVisit(id){try{await fetch('/api/confirm/'+id,{method:'POST'});visits();}catch(_){}}
async function visits(){try{const r=await fetch('/api/visits');const d=await r.json();
  const tb=document.getElementById('visits');
  document.getElementById('empty').style.display=d.length?'none':'block';
  tb.innerHTML=d.map(v=>{
   const act=v.status==='confirmed'
     ?'<span class="pill ok">已放行 '+(v.confirmed_at?v.confirmed_at.slice(11,16):'')+'</span>'
     :'<span class="pill wait">待核对</span>';
   const btn=v.access_status==='blacklist'?'<span class="pill bad">⛔ 禁止放行</span>'
     :(v.status==='confirmed'?'':'<button class="go" onclick="confirmVisit('+v.id+')">放行</button>');
   const flag=v.access_status==='blacklist'?'<span class="pill bad">⛔黑名单</span> ':
              v.access_status==='whitelist'?'<span class="pill vip">✅白名单</span> ':'';
   const cls=seen.has(v.id)?'':'new'; seen.add(v.id);
   return '<tr class="'+cls+'"><td class="plate">'+flag+(v.plate||'—')+'</td><td>'+(v.company||'—')+
     '</td><td>'+(v.reason||'—')+'</td><td>'+(v.phone||'—')+'</td><td>'+(v.name||'—')+
     '</td><td class="muted">'+(v.entry_time||'—')+'</td><td>'+act+'</td><td>'+btn+'</td></tr>';
  }).join('');}catch(_){}}
visits();setInterval(visits,3000);
</script></body></html>"""


_VOICE_HTML = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>访客登记 · AI 门卫</title>
<script src="https://cdn.jsdelivr.net/npm/livekit-client/dist/livekit-client.umd.min.js"></script>
<style>
  *{box-sizing:border-box}
  body{margin:0;font-family:-apple-system,'Segoe UI',Roboto,'PingFang SC',sans-serif;
    min-height:100vh;display:flex;align-items:center;justify-content:center;color:#fff;
    background:linear-gradient(160deg,#2b6a5a 0%,#1f4f6b 55%,#243b66 100%)}
  .card{width:90%;max-width:380px;text-align:center;padding:8px}
  .logo{font-size:30px} h1{font-size:22px;margin:6px 0 2px;font-weight:700}
  .sub{color:rgba(255,255,255,.75);font-size:14px;line-height:1.6;margin:8px 0 30px}
  .orb{width:120px;height:120px;border-radius:50%;margin:0 auto 26px;position:relative;
    background:radial-gradient(circle at 50% 40%,#7fe9c4,#1ea672);display:flex;
    align-items:center;justify-content:center;font-size:42px;box-shadow:0 12px 40px rgba(30,166,114,.5)}
  .orb.idle{background:radial-gradient(circle at 50% 40%,#cfe0e6,#8aa1ad);box-shadow:none}
  .orb.live::after{content:'';position:absolute;inset:0;border-radius:50%;
    box-shadow:0 0 0 0 rgba(127,233,196,.6);animation:pulse 1.6s infinite}
  @keyframes pulse{to{box-shadow:0 0 0 26px rgba(127,233,196,0)}}
  button{font-size:17px;padding:16px 30px;border:0;border-radius:999px;cursor:pointer;font-weight:600;
    background:#fff;color:#1f4f6b;box-shadow:0 8px 24px rgba(0,0,0,.18)} button:disabled{opacity:.6}
  .hang{background:#e25b5b;color:#fff;margin-left:10px}
  .status{margin-top:22px;font-size:15px;min-height:24px;color:rgba(255,255,255,.92)}
  a{color:#9fe7cf}
</style></head><body>
<div class="card">
  <div class="logo">🐳</div>
  <h1>访客登记</h1>
  <div class="sub">点下方按钮，对着麦克风说话，<br>AI 门卫帮您登记入园 · 全程几句话</div>
  <div class="orb idle" id="mic">🎙️</div>
  <button id="btn">开始对话</button>
  <button id="hang" class="hang" style="display:none">挂断</button>
  <button id="snd" style="display:none;background:#ffd86b;color:#1f4f6b;margin-top:14px">🔊 点击启用声音</button>
  <div class="status" id="status"></div>
</div>
<script>
const btn=document.getElementById('btn'),hang=document.getElementById('hang'),
      st=document.getElementById('status'),mic=document.getElementById('mic'),
      snd=document.getElementById('snd');
let room; const pending=[];
function reset(){mic.className='orb idle';mic.textContent='🎙️';hang.style.display='none';btn.disabled=false;btn.style.display='inline-block';snd.style.display='none';pending.length=0;}
// Autoplay is often blocked until a user gesture. Instead of silently failing
// (the "没有声音" trap), reveal a visible button so the visitor can enable sound.
function tryPlay(el){ if(!el||!el.play) return;
  el.play().catch(()=>{ pending.push(el); snd.style.display='inline-block';
    st.innerHTML='🔇 浏览器拦截了自动播放——请点上方<b>「启用声音」</b>'; }); }
snd.onclick=()=>{ pending.forEach(el=>el.play().catch(()=>{})); pending.length=0;
  snd.style.display='none'; st.innerHTML='已接通，门卫会先开口——请直接说话'; };
btn.onclick=async()=>{
  btn.disabled=true; st.textContent='正在接入…';
  try{
    const id='visitor-'+Math.random().toString(36).slice(2,8);
    const r=await fetch('/token?room=voice-demo&identity='+id);
    const d=await r.json(); if(d.error){throw new Error(d.error);}
    room=new LivekitClient.Room();
    room.on(LivekitClient.RoomEvent.TrackSubscribed,(track)=>{
      if(track.kind==='audio'){const el=track.attach();el.autoplay=true;
        el.setAttribute('playsinline','');el.muted=false;document.body.appendChild(el);
        tryPlay(el);}});
    room.on(LivekitClient.RoomEvent.Disconnected,()=>{st.textContent='已挂断';reset();});
    await room.connect(d.url,d.token);
    await room.localParticipant.setMicrophoneEnabled(true);
    mic.className='orb live'; mic.textContent='🔊';
    btn.style.display='none'; hang.style.display='inline-block';
    st.innerHTML='已接通，门卫会先开口——请直接说话';
  }catch(e){st.textContent='接入失败：'+e.message+'（确认 .env 里 LiveKit 配置 + agent worker 已启动）';btn.disabled=false;}
};
hang.onclick=async()=>{try{await room.disconnect();}catch(_){}st.textContent='已挂断';reset();};
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


_GUARD_CALL_HTML = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>保安介入通话</title>
<script src="https://cdn.jsdelivr.net/npm/livekit-client/dist/livekit-client.umd.min.js"></script>
<style>
  body{margin:0;font-family:-apple-system,Segoe UI,'PingFang SC',sans-serif;background:#f4f1ea;
    color:#2b2b2b;display:flex;min-height:100vh;align-items:center;justify-content:center}
  .card{background:#fff;border-radius:20px;box-shadow:0 10px 40px rgba(0,0,0,.08);padding:32px 40px;
    text-align:center;max-width:420px;width:90%}
  h1{font-size:19px;margin:0 0 6px} p{color:#777;font-size:14px}
  button{font-size:16px;padding:14px 28px;border:0;border-radius:999px;background:#c9742e;color:#fff;cursor:pointer}
  .status{margin-top:16px;font-size:14px;color:#555;min-height:22px}
</style></head><body>
<div class="card">
  <h1>👮 保安介入通话</h1>
  <p id="room">房间：—</p>
  <button id="btn">接入并对讲</button>
  <button id="hang" style="display:none;background:#c62828;margin-left:8px">挂断</button>
  <div class="status" id="status">接入后 AI 会让位，由你和访客直接对话</div>
</div>
<script>
const q=new URLSearchParams(location.search); const roomName=q.get('room');
document.getElementById('room').textContent='房间：'+(roomName||'缺少 room 参数');
const btn=document.getElementById('btn'),hang=document.getElementById('hang'),st=document.getElementById('status');
let rm;
btn.onclick=async()=>{ if(!roomName){st.textContent='缺少 room 参数';return;}
  btn.disabled=true; st.textContent='接入中…';
  try{
    const id='guard-'+Math.random().toString(36).slice(2,7);
    const r=await fetch('/token?room='+encodeURIComponent(roomName)+'&identity='+id);
    const d=await r.json(); if(d.error)throw new Error(d.error);
    rm=new LivekitClient.Room();
    rm.on(LivekitClient.RoomEvent.TrackSubscribed,(t)=>{if(t.kind==='audio'){
      const el=t.attach();el.autoplay=true;el.setAttribute('playsinline','');document.body.appendChild(el);el.play&&el.play().catch(()=>{});}});
    rm.on(LivekitClient.RoomEvent.Disconnected,()=>{st.textContent='已挂断';hang.style.display='none';btn.disabled=false;});
    await rm.connect(d.url,d.token);
    await rm.localParticipant.setMicrophoneEnabled(true);
    hang.style.display='inline-block';
    st.innerHTML='✅ 已接入，AI 正在让位——请直接和访客对话。';
  }catch(e){st.textContent='接入失败：'+e.message;btn.disabled=false;}
};
hang.onclick=async()=>{try{await rm.disconnect();}catch(_){}st.textContent='已挂断';hang.style.display='none';btn.disabled=false;};
</script></body></html>"""


_ASK_HTML = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>门卫数据中心</title>
<style>
  :root{--bg:#eef1f6;--card:#fff;--ink:#1f2733;--muted:#8a94a6;--accent:#1ea672;--line:#e9edf3}
  *{box-sizing:border-box} html,body{height:100%}
  body{margin:0;font-family:-apple-system,'Segoe UI',Roboto,'PingFang SC',sans-serif;background:var(--bg);
    color:var(--ink);display:flex;flex-direction:column}
  header{padding:12px 22px;display:flex;align-items:center;gap:14px;background:#fff;border-bottom:1px solid var(--line)}
  header h1{font-size:17px;margin:0}
  .tabs{display:flex;gap:6px;background:#f3f6fb;border-radius:999px;padding:4px}
  .tab{border:0;background:transparent;color:#566;font-size:14px;padding:7px 16px;border-radius:999px;cursor:pointer}
  .tab.on{background:var(--accent);color:#fff;font-weight:600}
  header .links{margin-left:auto;display:flex;gap:8px}
  header a{color:#566;text-decoration:none;font-size:13px;background:#f3f6fb;border:1px solid #e7ecf4;
    padding:7px 12px;border-radius:999px}
  .panel{flex:1;min-height:0;display:flex;flex-direction:column}
  /* ---- chat ---- */
  .chat{flex:1;overflow:auto;padding:20px;max-width:800px;width:100%;margin:0 auto}
  .msg{display:flex;margin:10px 0} .msg.me{justify-content:flex-end}
  .bub{max-width:80%;padding:11px 15px;border-radius:16px;font-size:15px;line-height:1.65;white-space:pre-wrap}
  .me .bub{background:var(--accent);color:#fff;border-bottom-right-radius:5px}
  .ai .bub{background:#fff;box-shadow:0 4px 16px rgba(20,30,50,.06);border-bottom-left-radius:5px}
  .hint{color:var(--muted);font-size:13px;text-align:center;margin:18px 0 8px}
  .chips{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;max-width:640px;margin:0 auto}
  .chip{background:#fff;border:1px solid #e7ecf4;color:#48566b;border-radius:999px;padding:8px 14px;font-size:13px;cursor:pointer}
  .chip:hover{background:#eef3fb}
  .bar{border-top:1px solid var(--line);background:#fff;padding:12px 20px}
  .brow{display:flex;gap:10px;max-width:800px;margin:0 auto}
  input,select{font-size:15px;padding:11px 14px;border:1px solid #dde3ec;border-radius:10px;outline:none;background:#fff}
  input:focus,select:focus{border-color:var(--accent)}
  .brow input{flex:1}
  .send{border:0;border-radius:10px;background:var(--accent);color:#fff;padding:0 22px;font-size:15px;font-weight:600;cursor:pointer}
  .send:disabled{opacity:.6}
  .spin{display:inline-block;width:15px;height:15px;border:2px solid #cfe;border-top-color:var(--accent);
    border-radius:50%;animation:s .8s linear infinite;vertical-align:-2px} @keyframes s{to{transform:rotate(360deg)}}
  /* ---- structured query ---- */
  .qwrap{flex:1;overflow:auto;padding:20px;max-width:980px;width:100%;margin:0 auto}
  .filters{background:#fff;border-radius:16px;box-shadow:0 6px 24px rgba(20,30,50,.06);padding:16px 18px;
    display:flex;flex-wrap:wrap;gap:10px;align-items:center}
  .seg{display:flex;gap:4px;background:#f3f6fb;border-radius:10px;padding:4px}
  .seg button{border:0;background:transparent;padding:7px 13px;border-radius:8px;font-size:14px;cursor:pointer;color:#566}
  .seg button.on{background:#fff;color:var(--ink);font-weight:600;box-shadow:0 1px 4px rgba(0,0,0,.08)}
  .stat{display:flex;gap:14px;margin:16px 0}
  .scard{background:#fff;border-radius:14px;box-shadow:0 6px 24px rgba(20,30,50,.06);padding:14px 20px;flex:1}
  .scard .n{font-size:26px;font-weight:800;color:var(--accent)} .scard .l{color:var(--muted);font-size:13px}
  .hours{background:#fff;border-radius:14px;box-shadow:0 6px 24px rgba(20,30,50,.06);padding:14px 18px;margin-bottom:16px}
  .hours .bars{display:flex;align-items:flex-end;gap:3px;height:70px;margin-top:8px}
  .hours .bar2{flex:1;background:#cfeede;border-radius:3px 3px 0 0;min-height:2px} .hours .bar2.hot{background:var(--accent)}
  .tbl{background:#fff;border-radius:14px;box-shadow:0 6px 24px rgba(20,30,50,.06);overflow:hidden}
  table{width:100%;border-collapse:collapse;font-size:14px}
  th{text-align:left;color:var(--muted);font-weight:600;font-size:12px;padding:11px 14px;background:#fafbfd}
  td{padding:12px 14px;border-top:1px solid #eef1f6}
  .pill{font-size:12px;padding:3px 10px;border-radius:999px}
  .pill.ok{background:#e7f6ef;color:#1ea672} .pill.wait{background:#fdf3e3;color:#c77b1a}
  .empty{padding:30px;text-align:center;color:var(--muted)}
</style></head><body>
<header><h1>📊 门卫数据中心</h1>
  <div class="tabs"><button class="tab on" data-t="chat">💬 对话</button><button class="tab" data-t="query">🔎 筛选查询</button></div>
  <div class="links"><a href="/admin" target="_blank">🏆 常客</a><a href="/dashboard">← 控制台</a></div>
</header>

<!-- 对话模式 -->
<div class="panel" id="panel-chat">
  <div class="chat" id="chat">
    <div id="welcome"><div class="hint">和 AI 对话查访客数据，支持追问（如"那上个月呢？"）</div>
    <div class="chips" id="chips"></div></div>
  </div>
  <div class="bar"><div class="brow">
    <input id="q" placeholder="例如：这个月有多少辆车被放行？">
    <button class="send" id="go">发送</button>
    <button class="send" id="new" style="background:#f3f6fb;color:#566">＋新对话</button>
  </div></div>
</div>

<!-- 筛选查询模式（确定性，不走 LLM） -->
<div class="panel" id="panel-query" style="display:none">
  <div class="qwrap">
    <div class="filters">
      <div class="seg" id="seg-range">
        <button data-r="today">今天</button><button data-r="week">本周</button>
        <button data-r="month" class="on">本月</button><button data-r="all">全部</button></div>
      <input id="f-company" placeholder="来访单位（可空）" style="width:160px">
      <input id="f-plate" placeholder="车牌（可空）" style="width:130px">
      <select id="f-status"><option value="">全部状态</option><option value="confirmed">已放行</option><option value="pending">待核对</option></select>
      <button class="send" id="run">查询</button>
    </div>
    <div class="stat">
      <div class="scard"><div class="n" id="s-count">—</div><div class="l">符合条件车辆</div></div>
      <div class="scard"><div class="n" id="s-released">—</div><div class="l">其中已放行</div></div>
    </div>
    <div class="hours"><div class="l" style="color:#8a94a6;font-size:13px">访问时段分布（0–23 时）</div>
      <div class="bars" id="bars"></div></div>
    <div class="tbl"><table><thead><tr><th>车牌</th><th>来访单位</th><th>事由</th><th>手机</th><th>时间</th><th>状态</th></tr></thead>
      <tbody id="rows"></tbody></table><div class="empty" id="q-empty" style="display:none">没有符合条件的记录</div></div>
  </div>
</div>

<script>
// ---- tabs ----
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('on',x===t));
  document.getElementById('panel-chat').style.display=t.dataset.t==='chat'?'':'none';
  document.getElementById('panel-query').style.display=t.dataset.t==='query'?'':'none';
  if(t.dataset.t==='query') runQuery();
});

// ---- chat mode ----
const EX=["这个月有多少辆车被放行？","本周一共多少访问车辆？","这个月找蓝色鲸鱼的有多少人？",
          "什么时间段访问最多？","张师傅这个月来了几次？","常客前五是谁？"];
const chat=document.getElementById('chat'),q=document.getElementById('q'),go=document.getElementById('go'),
      chips=document.getElementById('chips'),welcome=document.getElementById('welcome');
let history=[];
chips.innerHTML=EX.map(t=>'<span class="chip">'+t+'</span>').join('');
chips.querySelectorAll('.chip').forEach(c=>c.onclick=()=>{q.value=c.textContent;send();});
document.getElementById('new').onclick=()=>{history=[];chat.querySelectorAll('.msg').forEach(m=>m.remove());welcome.style.display='';};
function bubble(role,text){const m=document.createElement('div');m.className='msg '+(role==='user'?'me':'ai');
  const b=document.createElement('div');b.className='bub';b.textContent=text;m.appendChild(b);
  chat.appendChild(m);chat.scrollTop=chat.scrollHeight;return b;}
async function send(){const question=q.value.trim(); if(!question||go.disabled)return;
  welcome.style.display='none'; q.value=''; bubble('user',question);
  const b=bubble('ai',''); b.innerHTML='<span class="spin"></span> 正在查…'; go.disabled=true;
  try{const r=await fetch('/guard/query',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({question,history})});
    const d=await r.json(); const a=d.answer||d.error||'(无结果)';
    b.textContent=a; history.push({role:'user',content:question}); history.push({role:'assistant',content:a});
  }catch(e){b.textContent='出错了：'+e.message;} go.disabled=false; q.focus();}
go.onclick=send; q.addEventListener('keydown',e=>{if(e.key==='Enter')send();});

// ---- structured filter mode ----
let curRange='month';
document.querySelectorAll('#seg-range button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('#seg-range button').forEach(x=>x.classList.toggle('on',x===b));
  curRange=b.dataset.r; runQuery();});
document.getElementById('run').onclick=runQuery;
['f-company','f-plate'].forEach(id=>document.getElementById(id).addEventListener('keydown',e=>{if(e.key==='Enter')runQuery();}));
document.getElementById('f-status').onchange=runQuery;
async function runQuery(){
  const p=new URLSearchParams({range:curRange,company:document.getElementById('f-company').value.trim(),
    plate:document.getElementById('f-plate').value.trim(),status:document.getElementById('f-status').value,limit:'100'});
  try{const r=await fetch('/api/query?'+p.toString()); const d=await r.json();
    document.getElementById('s-count').textContent=d.count;
    document.getElementById('s-released').textContent=d.released;
    // hour histogram
    const by=d.by_hour||{}; let max=1; for(let h=0;h<24;h++) max=Math.max(max,by[h]||0);
    let bars=''; for(let h=0;h<24;h++){const v=by[h]||0; const hot=v===max&&v>0;
      bars+='<div class="bar2'+(hot?' hot':'')+'" style="height:'+Math.round((v/max)*100)+'%" title="'+h+'时: '+v+'"></div>';}
    document.getElementById('bars').innerHTML=bars;
    const tb=document.getElementById('rows'); const vs=d.visits||[];
    document.getElementById('q-empty').style.display=vs.length?'none':'block';
    tb.innerHTML=vs.map(v=>{const st=v.status==='confirmed'?'<span class="pill ok">已放行</span>':'<span class="pill wait">待核对</span>';
      const bl=v.access_status==='blacklist'?' ⛔':v.access_status==='whitelist'?' ✅':'';
      return '<tr><td>'+(v.plate||'—')+bl+'</td><td>'+(v.company||'—')+'</td><td>'+(v.reason||'—')+
        '</td><td>'+(v.phone||'—')+'</td><td style="color:#8a94a6">'+(v.entry_time||'—')+'</td><td>'+st+'</td></tr>';}).join('');
  }catch(e){document.getElementById('rows').innerHTML='<tr><td colspan=6 style="color:#c62828">查询出错：'+e.message+'</td></tr>';}
}
</script></body></html>"""


def main() -> None:
    import os

    import uvicorn
    from dotenv import load_dotenv

    load_dotenv()  # make .env values (DB, notify, Hikvision, LiveKit) visible
    get_settings.cache_clear()
    cfg = get_settings()
    # Cloud platforms (Railway/Render/Fly) inject the listen port via $PORT.
    port = int(os.environ.get("PORT", cfg.web_port))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
