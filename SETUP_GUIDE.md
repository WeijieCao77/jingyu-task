# 🧭 你要做的：账号 + 操作 + 一键 Prompt（v0.23 总指南）

> 这一份是**给你（人）**看的：需要哪些账号、每一步怎么操作、要花多少钱，以及**凡是要本地 Claude Code（你 Windows 机器上那个）干的活，都配好可直接复制的 prompt**。
> 原则不变：**除了"花钱 / 注册账号 / 在网页上点几下"，其余全部交给本地 CC 自动完成。**
> 细节专题：拿密钥图文 `USER_TODO.md`；通知 `NOTIFY_SETUP.md`；电话 `TELEPHONY.md`；首跑排查 `SMOKE_CHECK.md`。

---

## 0. 总览：你要准备哪些账号（按需，不是全都要）

| 账号 / 密钥 | 必填？ | 用途 | 费用 | 填到 `.env` 的 |
|---|---|---|---|---|
| **OpenAI API Key** | ✅ 必填 | 语音大脑（realtime / STT+LLM+TTS） | 用多少付多少；测一通电话 ≈ ¥1-3 | `OPENAI_API_KEY` |
| **Telegram Bot** | ⭐ 推荐 | 保安手机即时收访客卡片 + 放行 | 免费 | `TELEGRAM_BOT_TOKEN` `TELEGRAM_CHAT_ID` |
| **LiveKit Cloud** | ☎️ 要"打电话进来"才需要 | 电话媒体 + SIP 接入（本地 dev server 公网打不进来） | 免费额度够 demo | `LIVEKIT_URL/API_KEY/API_SECRET` |
| **Twilio** | ☎️ 要"打电话进来"才需要 | 提供那个"入园电话号码" | 号码 ≈ $1.15/月 + 通话 ≈ $0.0085/分；注册送 ~$15 | `SIP_INBOUND_NUMBER` |
| roster.json / access.json | 可选 | 公司名单纠正 / 黑白名单 | 免费（你自己列） | `ROSTER_PATH` `ACCESS_LIST_PATH` |

> **最小起步**：只配 OpenAI + Telegram → 浏览器 `/voice` 说话 + 手机收卡片 + 放行，全链路就通了（不用电话）。
> **要"拨打手机号"那条**（任务第一必交项）→ 再加 LiveKit Cloud + Twilio（见 §1.3 / §1.4 / §3.4）。

---

## 1. 拿密钥 / 账号（你在网页上操作的部分）

### 1.1 OpenAI（✅ 必填）
1. 打开 https://platform.openai.com → 注册/登录。
2. 右上 **Settings → Billing** → 充值（建议先充 $5，够测很多次）。
3. 左侧 **API keys → Create new secret key** → 复制（`sk-...`，**只显示一次**）。
4. （realtime 提速需要）该 key 默认就能用 `gpt-realtime`；若调用报无权限，把 `.env` 改 `VOICE_MODE=pipeline` 即可照常跑（慢一点）。
> 这一个 key 同时供 realtime / STT / LLM / TTS——**唯一一定要的密钥**。

### 1.2 Telegram（⭐ 推荐，5 分钟，手机即时收消息）
1. 手机/电脑 Telegram 搜 **@BotFather** → 发 `/newbot` → 起名字 → 拿到 **bot token**（`12345:ABC...`）。
2. 搜你刚建的 bot，**给它发一句话**（如 "hi"，否则取不到 chat id）。
3. chat id 这一步**交给本地 CC**（见 Prompt 2.2，它会帮你请求 getUpdates 解析出来）。
> 想发到**企业微信**群：群 → 群机器人 → 复制 Webhook，填 `WECOM_WEBHOOK_URL`、`NOTIFY_CHANNEL=telegram,wecom` 可同时推。详见 `NOTIFY_SETUP.md`。

### 1.3 LiveKit Cloud（☎️ 仅"打电话进来"需要，免费）
1. 打开 https://cloud.livekit.io → 注册 → **Create Project**。
2. 项目 **Settings / Keys** 里复制三样：`wss://<你的项目>.livekit.cloud`、**API Key**、**API Secret**。
3. 项目里找 **SIP** 页，记下你的 **SIP 主机名**（形如 `<项目>.sip.livekit.cloud`，§1.4 Twilio 要用）。
> 为什么必须用 Cloud：你本地 `livekit-server.exe --dev` 是回环地址，Twilio 从公网打不进来。worker 仍可在你本机跑（它是外连 Cloud，不需要公网入站）。

### 1.4 Twilio（☎️ 仅"打电话进来"需要，给号码）
1. 打开 https://www.twilio.com → 注册（送试用额度）。
2. **Phone Numbers → Buy a number** → 选一个支持 **Voice** 的号码买下（≈ $1.15/月）。
3. 这个号码就是"入园张贴的电话"。**接到 LiveKit 的具体配置（TwiML / SIP origination）让本地 CC 带你做**（见 Prompt 3.4 + `TELEPHONY.md` §三）。
> 国内 +86 落地：Twilio 不易发 +86，生产换阿里云/容联等国内 SIP 中继，**LiveKit SIP 这层不变**（`TELEPHONY.md` §四）。demo 用 Twilio 国际号验证全链路即可。

### 1.5（可选）公司名单 / 黑白名单
- 公司名单：仓库已带 `roster.example.json`（22 家）；要用你真实名单就照格式改成 `roster.json`。
- 黑白名单：仓库已带 `access.example.json`；按格式填你的黑/白名单车牌或手机。
- 这两个**只是 JSON 文件**，本地 CC 可帮你建/改。

---

## 2. 交给本地 Claude Code：起服务 + 自测（复制下面 prompt）

> 先把上面拿到的密钥准备好，本地 CC 会问你要、写进 `.env`、起服务、报错自查。

### 📋 Prompt 2.1 —— 同步代码 + 起服务 + 浏览器先跑通（不用电话）
```
这是园区语音访客登记项目，分支 claude/voice-agent-takehome-qzjbd2。请：
1. git pull origin claude/voice-agent-takehome-qzjbd2 同步到最新(v0.23)。
2. 在 x64 venv 装依赖：pip install -r requirements.txt；按 SMOKE_CHECK.md §C5 处理 Windows/ARM64。
3. 问我要 OPENAI_API_KEY，写进 .env；设 VOICE_MODE=realtime（若该 key 没有 gpt-realtime 权限就回退 pipeline 并告诉我）。
4. 起本地 LiveKit（livekit-server.exe --dev）、web server、agent worker(dev) 三个进程。
5. 让我打开 http://localhost:8080/voice 点"开始对话"实测：AI 是否 1~2 秒开口、对话是否自然、
   登记完后 http://localhost:8080/dashboard 是否出现这条记录、点"放行"是否抬杆(stub 打印)。
6. 跑 PYTHONPATH=src pytest -q 应 76 passed。把结果和任何报错告诉我，报错先自查再问我。
```

### 📋 Prompt 2.2 —— 配 Telegram 推送 + 自测（手机收卡片）
```
帮我把 Telegram 推送配好并自测，让我手机收到访客卡片。
1. 我已用 @BotFather 建 bot，问我要 TELEGRAM_BOT_TOKEN。
2. 让我先给 bot 发一句话，然后你请求 https://api.telegram.org/bot<token>/getUpdates，
   帮我解析出 chat id，填进 .env 的 TELEGRAM_CHAT_ID。
3. 写 .env：NOTIFY_CHANNEL=telegram；PUBLIC_BASE_URL 用我手机能访问的地址
   （cloudflared 隧道的 https，或本机 Tailscale IP 如 http://100.x.x.x:8080；
    别用 localhost——代码会兜底但按钮会没了）。
4. 自测(不用打电话)：PYTHONPATH=src python -m visitor_agent.sim.run_text --scenario scenarios/songhuo.json --live
   确认我手机 Telegram 收到访客卡片 + 「确认放行」按钮；点一下能否放行。把结果告诉我。
```

---

## 3. 功能验证（每块一个 prompt，挑你想看的发）

### 📋 Prompt 3.1 —— realtime 提速 + 浏览器语音
```
把 .env 设 VOICE_MODE=realtime，重启 agent worker。我打开 /voice 说话，帮我观测：
首句多快出来(目标≈1.4s)、每轮是否还"卡"、中文/数字识别准不准、登记结尾 AI 有没有复述车牌(逐位)和手机(分组)让我确认。
再切 VOICE_MODE=pipeline 对比一次，告诉我两者差别。
```

### 📋 Prompt 3.2 —— 公司名单 + 黑白名单（含黑名单"登记不放行"）
```
.env 设 ROSTER_PATH=roster.json（或仓库的 roster.example.json）、ACCESS_LIST_PATH=access.example.json，重启 worker+web。
在 /voice 里依次测三种，告诉我每种后台/Telegram 卡片表现：
1) 故意说错"蓝色金鱼科技"→ 应被纠成"蓝色鲸鱼科技"、AI 主动确认。
2) 报白名单车牌 沪A12345 → 卡片/后台显示 ✅白名单，但仍需我点放行(不自动)。
3) 报黑名单车牌 沪A00000 → 卡片/后台显示 ⛔黑名单，后台该行是「⛔禁止放行」不能点放行，
   点确认链接也显示"禁止放行"、栏杆不抬。把三种的后台截图发我。
```

### 📋 Prompt 3.3 —— 放行后 AI 语音通知访客（FR-2）
```
我在 /voice 通话中完成一次登记后，在 /dashboard 点"放行"（或点 Telegram 卡片确认链接）。
验证：我这端的 AI 是否开口说"已为您放行，请进，栏杆已抬起"。pipeline 和 realtime 各测一次。
若我已挂断则应静默不报错。把 agent 日志里 data_received/approved 那几行发我。
```

### 📋 Prompt 3.5 —— 门卫数据助手（对话式查询，无需额外账号）
```
起 web server 后我打开 http://localhost:8080/ask（或 /dashboard 右上「🔎 数据查询」）。
先用 /voice 或 sim --live 造几条访客、放行其中一两条，然后让我在 /ask 里像聊天一样问：
"这个月有多少辆车被放行？""那本周呢？""找蓝色鲸鱼的有多少人？""什么时段最多？"
验证：能多轮追问（"那本周呢"会接着上文）、数字对得上。它走 LLM，需要 .env 里的 OPENAI_API_KEY。
```

### 📋 Prompt 3.6 —— 门卫专属访问（访客不能查数据）
```
帮我设门卫专属访问并自测两路：
1. 网页：.env 设 GUARD_ACCESS_KEY=<我给的口令>，重启 web。验证：访客 /voice 仍能开；
   但 /dashboard /ask /admin 会跳到 /login，输对口令后才进；输错进不去。
2. 电话（若已通电话路）：.env 设 GUARD_PHONES=<我的门卫手机号>。我用这个号码拨入园电话，
   验证 AI 变成"数据助手"问我想查什么（而不是登记）；换个非门卫号码拨则照常走访客登记。
```

### 📋 Prompt 3.4 —— ☎️ 电话拨号进来（任务第一必交项，需 LiveKit Cloud + Twilio）
```
帮我把"打电话给 AI 门卫"在我本机跑通，完整步骤见仓库 TELEPHONY.md。我有 Twilio 和 LiveKit Cloud。
1. 装 lk CLI 并 lk cloud auth；把我 LiveKit Cloud 项目的 LIVEKIT_URL/API_KEY/SECRET 写进 .env，
   VOICE_MODE=realtime、填 OPENAI_API_KEY、NOTIFY_CHANNEL=telegram（按 NOTIFY_SETUP.md 配好）。
2. 带我在 Twilio 把买好的号码接到 LiveKit：用 TwiML Bin
   <Response><Dial><Sip>sip:<我的LiveKit-SIP主机></Sip></Dial></Response> 指过去
   （SIP 主机名在 LiveKit Cloud 控制台 SIP 页，帮我确认）。问我要这个电话号码。
3. 跑 SIP_INBOUND_NUMBER=<我的号码> ./scripts/setup_sip.sh 建入站 trunk + dispatch rule；
   若我的 lk 版本 JSON 字段不一致，按 docs.livekit.io/sip 调整后重试，把最终用的 JSON 给我。
4. 起 agent worker(start，连 Cloud) + web server。让我用手机拨打那个号码实测：
   AI 是否 1~2s 开口、是否把我的来电号码预填成手机号、25 秒内我手机是否收到卡片、放行后电话里是否听到"已放行"。
5. 每步命令输出 + 我要点的地方写清楚，报错先自查再问我。最后告诉我整通电话从接通到微信卡片用了几秒。
```

---

## 4. 费用预期（demo 量级）
- **OpenAI**：realtime ≈ $0.18-0.46/分；一通 1 分钟的电话 ≈ ¥1-3。先充 $5 够测很多次。
- **LiveKit Cloud**：免费额度覆盖 demo。
- **Twilio**：号码 ≈ $1.15/月 + 通话 ≈ $0.0085/分；注册送 ~$15 试用额度。
- **Telegram / 名单文件**：免费。
> 不想花电话的钱：浏览器 `/voice` + Telegram 就能演示完整产品逻辑，电话路单独验证。

## 5. 常见坑（先看这里）
- **Telegram 卡片发不出** → `PUBLIC_BASE_URL` 别用 localhost（Telegram 拒绝 localhost 按钮）；用隧道/Tailscale IP。代码已兜底降级纯文本，但按钮会没。
- **电话接通没人说话** → `LIVEKIT_URL` 必须是 **Cloud**（不是本地 dev）；agent worker 要在跑。
- **首句慢/超 25s** → 确认 `VOICE_MODE=realtime` 且 key 有 gpt-realtime 权限。
- **黑名单还能放行？** → 确认 `ACCESS_LIST_PATH` 指对、车牌在黑名单里（系统会拒绝放行）。
- **每次测试数据像被清空 / 回访识别不到老访客** → 原因是 SQLite 相对路径随你启动目录变。现已**自动锚定项目根目录**，agent 和 web 用同一个文件；启动日志会打印 `SQLite database at <绝对路径>`，确认两个进程打印的是同一个。想彻底稳妥就在 `.env` 填**绝对路径**或用 Neon Postgres。**备份**=直接复制那个 `.db` 文件。
- **Windows / ARM64 / 无 Docker** → 一律照 `SMOKE_CHECK.md §C5`。

---

✅ 你点几下网页 + 把 prompt 丢给本地 CC，剩下让它自动跑。测出来任何不对，把现象发我（GitHub 侧），我改代码 + 补单测 + push。
