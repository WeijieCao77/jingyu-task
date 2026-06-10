# 📱 扫码版 Demo（手机扫码 → 直接和 AI 门卫对话）

目标：入口贴一张二维码，访客**用手机扫码就打开语音页、对着手机说话完成登记**，你在电脑后台看实时效果。

> 关键现实：手机要能连上语音，**LiveKit 必须公网可达**。本地 Docker 的 `--dev` 只在你电脑本机能连，
> 手机（尤其移动网络）连不到。所以扫码版有两条路 —— **路 A 最稳，推荐明天就用路 A**。

---

## 路 A（推荐 · 任何网络都能扫）= LiveKit Cloud 免费账号 + 免账号隧道

需要你提供的：① `OPENAI_API_KEY`（已有）② 一个 **LiveKit Cloud 免费账号**（免费、不花钱，拿 3 个值，教程见 USER_TODO.md）。
其余全自动。把下面整段喂给本地 Claude Code：

```
帮我把"扫码版"语音 demo 跑起来，让我用手机扫码就能和 AI 门卫对话。
我提供：OPENAI_API_KEY，以及 LiveKit Cloud 的 LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET。

1. 装依赖（若还没装）：python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
   并 PYTHONPATH=src python -m visitor_agent.agent download-files
2. 写 .env：
   OPENAI_API_KEY=<我给的>
   LLM_PROVIDER=openai
   LLM_MODEL=gpt-4o-mini
   LIVEKIT_URL=<我给的 wss://...livekit.cloud>
   LIVEKIT_API_KEY=<我给的>
   LIVEKIT_API_SECRET=<我给的>
   NOTIFY_CHANNEL=none
3. 起一个免账号公网隧道暴露网页（cloudflared quick tunnel）：
   ./scripts/run_tunnel.sh 8080
   记下它打印的 https 地址，写回 .env 的 PUBLIC_BASE_URL=<那个 https 地址>
4. 起服务：
   终端A: PYTHONPATH=src python -m visitor_agent.web.server
   终端B: PYTHONPATH=src python -m visitor_agent.agent dev   （确认连上 LiveKit）
5. 给我两个链接：
   · 二维码页（电脑打开，给我看二维码）: <PUBLIC_BASE_URL>/qr
   · 后台 Dashboard（电脑打开）: http://localhost:8080/dashboard
6. 告诉我：用手机摄像头扫二维码 → 手机浏览器打开语音页 → 点"接入门卫"、允许麦克风 →
   AI 先开口，我对着手机说车牌/公司/事由/手机号 → 我在电脑 Dashboard 看实时字幕和采集字段，
   然后在 Dashboard 点"放行"。请确认这条链路在我手机上真的发生了。
任何报错你先自查修复（不改架构），需要我点的地方写清楚。
```

## 路 B（零账号 · 仅限手机和电脑在同一 WiFi）= 本地 LiveKit + 局域网

不想注册任何账号、且手机能和电脑连同一个 WiFi 时用。喂给本地 Claude Code：

```
帮我用"本地 LiveKit + 同一 WiFi"的方式跑扫码版，不要任何云账号。我只提供 OPENAI_API_KEY。
1. 查我电脑在局域网的 IP（如 192.168.x.x），记为 LANIP。
2. 用局域网 IP 起本地 LiveKit（让手机也能连）：
   docker run -d --name livekit-dev -p 7880:7880 -p 7881:7881 -p 50000-50050:50000-50050/udp \
     livekit/livekit-server --dev --node-ip <LANIP>
3. 写 .env：
   OPENAI_API_KEY=<我给的>；LLM_PROVIDER=openai；LLM_MODEL=gpt-4o-mini
   LIVEKIT_URL=ws://<LANIP>:7880；LIVEKIT_API_KEY=devkey；LIVEKIT_API_SECRET=secret
   NOTIFY_CHANNEL=none；PUBLIC_BASE_URL=http://<LANIP>:8080
4. 起服务（web 绑 0.0.0.0 已默认）：
   终端A: PYTHONPATH=src python -m visitor_agent.web.server
   终端B: PYTHONPATH=src python -m visitor_agent.agent dev
5. 让我电脑打开 http://<LANIP>:8080/qr 看二维码；后台 http://<LANIP>:8080/dashboard。
6. 我手机连同一 WiFi、扫码 → 打开语音页对话 → 我在电脑 Dashboard 看效果并点放行。
注意：手机和电脑必须同一 WiFi；若连不上多半是防火墙挡了 7880/UDP 端口，请提示我放行。
```

---

## 验收时我会看到什么
- 手机：扫码 → 网页"🐳 和 AI 门卫对话" → 点接入 → 听到 AI 中文提问 → 我说话 → AI 追问/确认。
- 电脑后台 `/dashboard`：实时字幕（我说的 + AI 说的）、采集字段逐项亮起、访客记录出现"待确认"。
- 我点"✅放行" → 状态"已放行" + 抬杆事件。
- 计时：AI 开口 → 访客记录出现 ≤ 25 秒。

> 路 A 用 LiveKit Cloud 是因为它本身就是公网可达的媒体服务器，手机在任何网络都能连——这是扫码版"明天就能测"最稳的方式。本地 Docker 版（ACCEPTANCE_PROMPT.md）依然是"电脑本机浏览器"验收的最省事方式。
