# 🎬 验收用：一键起服务的 Prompt（复制给本地 Claude Code）

下载本仓库到本地后，**把下面整段**复制给你电脑上的 Claude Code。它会装好依赖、问你要密钥、起好服务，
让你**直接对着电脑麦克风和 AI 门卫说话**完成登记，并在后台 Dashboard 实时看到效果。

> 设计原则：**最基础流程"下载即用"**。语音 demo 用浏览器麦克风跑通（只需 LiveKit + 两个密钥，
> 不碰 Twilio）；真实电话号码(Twilio SIP)作为"精修"步骤放最后。

---

```
你是我的本地运行助手。这个仓库是一个"园区语音访客登记 Voice Agent"。
目标：让我能在浏览器里直接对着麦克风和 AI 门卫说话完成登记，并在后台 Dashboard 实时看到
对话字幕、采集字段、企业微信推送、保安确认、抬杆。请一步步做，需要密钥时停下问我，
不要把任何密钥写进会被提交的文件。

【1. 安装】
- python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
- mkdir -p data
- 预下载语音模型（VAD/turn detector），避免首次启动卡住：
  PYTHONPATH=src python -m visitor_agent.agent download-files

【2. 配置 .env（问我要这些值）】
- cp .env.example .env
- ANTHROPIC_API_KEY、OPENAI_API_KEY（LLM + 语音）
- 保安通知渠道：默认 NOTIFY_CHANNEL=discord，填 DISCORD_WEBHOOK_URL
  （Discord 频道设置 → 整合 → Webhook → 新建 → 复制 URL；美国可用、最省事，无需企业微信）
  也可改 NOTIFY_CHANNEL=telegram（填 TELEGRAM_BOT_TOKEN/CHAT_ID，带确认按钮）
- LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET（去 https://cloud.livekit.io 建项目拿，免费）
- PUBLIC_BASE_URL：先填 http://localhost:8080（保安确认链接本机点即可；要手机点再换公网隧道）

【3. 起两个进程】
- 终端A（后台 + 浏览器语音页 + 确认服务）：
  source .venv/bin/activate && PYTHONPATH=src python -m visitor_agent.web.server
- 终端B（语音 Agent worker，连 LiveKit 等待接入）：
  source .venv/bin/activate && PYTHONPATH=src python -m visitor_agent.agent dev
  确认它显示 registered / 已连接 LiveKit。

【4. 让我做最基础流程验收（语音，无需电话）】
- 让我用 Chrome 打开：http://localhost:8080/voice
- 另开一个标签页打开后台：http://localhost:8080/dashboard
- 我点"接入门卫"、允许麦克风。AI 应先开口："您好，请问车牌号多少，今天找哪家公司，什么事儿？"
- 我对着麦克风报：车牌、公司、事由、手机号（可以一句话说多项，测它像不像真人）。
- 你提醒我观察 Dashboard：对话字幕、采集字段、"推送门卫"应实时出现；Discord 频道应收到访客卡片。
- 我点卡片里的"✅确认放行"链接 → 浏览器显示"已放行" → Dashboard 出现"保安确认/抬杆"，
  访客记录状态变"已放行"。
- 用秒表测：从 AI 开口到企微卡片出现是否 ≤ 25 秒。

【5. 加分项验证】
- 回访识别：用同一车牌再走一遍语音登记，开场 AI 应识别为回访、直接确认而非从头重问。
- 门卫查询：PYTHONPATH=src python -m visitor_agent.guard_query "今天一共多少访问车辆？"
  以及 "什么时间段访问最多？" —— 看回答数字是否正确。

【6.（精修，可选）接真实电话 Twilio】
- 按 SETUP_CHECKLIST.md 第 5 步，把我的 Twilio 号码经 SIP 接到 LiveKit
  （参考 https://docs.livekit.io/telephony/accepting-calls/inbound-twilio/ ，
   用 lk CLI 建 inbound trunk + dispatch rule）。需要我在控制台点什么，明确告诉我。
- 配好后告诉我号码，我用手机拨打，重复第 4 步的观察（这次是真电话）。

【输出要求】
- 每步做完简短报结果，给我可点的链接（/voice、/dashboard）。
- 任何报错先贴原文，再做最小修复并说明改了什么（不要改架构）。
- 全部跑通后一句话总结：语音页地址、Dashboard 地址、企微效果、端到端耗时。
```

---

## 兜底路径（如果某步卡住）

- **连 LiveKit 都还没配好** → 先做纯文本版，照样能看到「采集→企微→确认→抬杆」全链路：
  ```
  PYTHONPATH=src python -m visitor_agent.web.server        # 开 /dashboard
  PYTHONPATH=src python -m visitor_agent.sim.run_text --scenario scenarios/songhuo.json --live
  ```
- **不想用我们自带的 /voice 页** → 也可用 LiveKit 官方 Agents Playground：起 agent worker 后，
  打开 https://agents-playground.livekit.io ，用你的 LiveKit 项目连接，进房间即可对话（agent 会自动加入）。
- **手机点确认链接** → 把 8080 用 ngrok/cloudflared 映射公网，把 https 地址填回 `.env` 的 `PUBLIC_BASE_URL` 并重启 web。

> 一句话：**最基础流程 = 浏览器说话 → 后台看到 → 微信收到 → 点确认放行**，只要 LiveKit + 两个密钥就能直接跑。电话是把"浏览器麦克风"换成"Twilio 号码"，属于精修。
