# ☁️ 全云端部署：彻底甩掉家里电脑，手机随处测

把整套跑到云上 → 手机从任何网络都能测语音/后台/转人工，**不需要家里电脑、不需要 Tailscale**。

## 架构（云端）
```
手机浏览器 ──HTTPS──▶ 云主机(Railway/Fly)：FastAPI 网页 + Agent Worker
   │                         │  └─ 出站连 OpenAI(STT/LLM/TTS)
   └──WebRTC实时音频──▶ LiveKit Cloud ◀──Agent Worker 作为参与者加入房间
                              │
                         Neon Postgres(数据持久)
```
要点：**手机直接连 LiveKit Cloud**（实时音频），云主机只需开 HTTP 端口；Agent Worker 在云主机常驻、出站连 LiveKit Cloud + OpenAI。无需开放 UDP、无需隧道。

---

## 一、你要开的账号（都有免费档；这是"账号/钱"那类，得你来）

| 服务 | 用途 | 拿什么 |
|---|---|---|
| **OpenAI** | STT+LLM+TTS | `OPENAI_API_KEY` |
| **LiveKit Cloud** https://cloud.livekit.io | 实时音频媒体服务器 | `LIVEKIT_URL`(wss://...) / `API_KEY` / `API_SECRET` |
| **Neon** https://neon.tech | 云 Postgres（数据持久） | 连接串 `postgresql://...`（建库时复制） |
| **Railway** https://railway.app（推荐，零配置）或 **Fly.io** | 跑 web+agent 常驻 | 部署后给你一个公网 https 域名 |

> Railway 按用量计费（有少量免费额度，约 $5/月够 demo）；Fly.io 有小机器免费额度。两者都"常驻不休眠"，适合一直在线等来电的 Agent。（Render 免费档会休眠 → Agent 掉线，不推荐免费档。）

---

## 二、部署步骤（Railway，最省事，GitHub 连接即部署）

1. Railway → New Project → **Deploy from GitHub repo** → 选 `WeijieCao77/jingyu-task`，分支 `main`。
2. Railway 检测到 `Dockerfile` 会自动构建（容器内同时跑 web + agent，见 `scripts/start.sh`）。
3. 在该服务的 **Variables** 里加环境变量：
   ```
   OPENAI_API_KEY=sk-...
   LLM_PROVIDER=openai
   LLM_MODEL=gpt-4o-mini
   LIVEKIT_URL=wss://<你的>.livekit.cloud
   LIVEKIT_API_KEY=<LiveKit Cloud key>
   LIVEKIT_API_SECRET=<LiveKit Cloud secret>
   DATABASE_URL=postgresql://<Neon 连接串>
   NOTIFY_CHANNEL=none
   ```
4. 部署成功后 Railway 给你一个域名（如 `https://xxx.up.railway.app`）。**再加一个变量并重部署**：
   ```
   PUBLIC_BASE_URL=https://xxx.up.railway.app      # 保安确认链接要用，必须是这个公网域名
   ```
5. 手机浏览器打开：
   - 访客 `https://xxx.up.railway.app/voice`
   - 后台 `https://xxx.up.railway.app/dashboard`
   - 常客 `https://xxx.up.railway.app/admin`

> Fly.io 版：装 `flyctl` → `fly launch --no-deploy`（已带 `fly.toml`）→ `fly secrets set OPENAI_API_KEY=... LIVEKIT_URL=... ...` → `fly deploy`，域名形如 `https://<app>.fly.dev`，同样把它设进 `PUBLIC_BASE_URL`。

---

## 三、交给 cowork / 云端 Claude Code 的部署 Prompt（可选）

如果你想让云端的 Claude Code 帮你跑完部署（你只在它要密钥/点授权时配合）：

```
请把这个仓库（visitor voice agent）全云端部署，让我手机随处能测，不要依赖任何本地电脑。
我会提供：OPENAI_API_KEY；LiveKit Cloud 的 URL/KEY/SECRET；Neon 的 DATABASE_URL。

1. 用 Railway（或 Fly.io）部署本仓库的 Dockerfile（容器内跑 web+agent，见 scripts/start.sh）。
   - 需要我登录/授权/连 GitHub 的地方，把链接和步骤清楚给我。
2. 设置环境变量：OPENAI_API_KEY、LLM_PROVIDER=openai、LLM_MODEL=gpt-4o-mini、
   LIVEKIT_URL/LIVEKIT_API_KEY/LIVEKIT_API_SECRET（LiveKit Cloud）、DATABASE_URL（Neon）、NOTIFY_CHANNEL=none。
3. 拿到部署域名后，把 PUBLIC_BASE_URL 设成那个 https 域名并重新部署。
4. 自检：访问 https://<域名>/health 返回 ok；确认日志里 agent worker 已连上 LiveKit Cloud（registered）。
5. 给我手机能点的三个链接：/voice、/dashboard、/admin，并告诉我怎么测（接入说话→后台看→点放行→转人工）。
报错先自查修复，改了什么说明；最后给我域名 + 三个链接 + 一句话状态。
```

---

## 四、验收（手机，任何网络）
- `/voice` 点接入、允许麦克风 → AI 中文开口 → 说话登记；
- `/dashboard` 看实时字幕/字段 → 点"✅放行" → 已放行 + 开闸时间；
- 转人工：对 AI 说"找真人"→ 后台 ⚠️转人工 + 介入；或后台"📞主动介入"任意来电；
- 计时：AI 开口 → 访客记录出现 ≤25 秒。

## 五、说明 / 取舍
- **这是"在云上跑"，不是"在你本地电脑跑"**——彻底不依赖家里电脑，代价是开三个云账号（都免费档起步）。
- 数据在 Neon（持久，重启不丢）。SQLite 仅适合单机本地，云端务必用 `DATABASE_URL=postgresql://...`。
- 通知默认 `none`（保安在 /dashboard 点放行）。想要外部推送可设 `NOTIFY_CHANNEL=discord` + `DISCORD_WEBHOOK_URL`。
- 抬杆仍是 stub（园区内网设备云端碰不到）；生产由园区侧网关回调或 VPN 接内网。
- 海康/真实电话(Twilio SIP) 等真实外设，按需在 LiveKit Cloud 侧接 SIP 中继。
