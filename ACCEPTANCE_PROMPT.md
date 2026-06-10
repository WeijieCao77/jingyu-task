# 🎬 验收：一段 Prompt 让本地 Claude Code 全自动起服务

**你只需要做一件事**：准备**一个** API key（`OPENAI_API_KEY`，全 OpenAI 跑通线路）——
怎么拿见 **[USER_TODO.md](USER_TODO.md)**（手把手图文教程）。手机扫码版见 **[QR_DEMO.md](QR_DEMO.md)**。

其余一切（装依赖、本地起 LiveKit、下载模型、配置、起服务、隧道）都由本地 Claude Code 完成。
**不需要你注册 LiveKit / Discord / 任何其他账号。** 保安通知默认走"后台 Dashboard 点放行"，零账号。

把下面整段复制给你电脑上的 Claude Code 即可：

---

```
你是我的本地运行助手。这个仓库是"园区语音访客登记 Voice Agent"。
目标：全自动把它跑起来，让我能在浏览器里对着麦克风和 AI 门卫对话完成登记，
并在后台 Dashboard 实时看到对话、采集字段，然后我在 Dashboard 上点"放行"。
除了我提供的两个 API key，其它你全部自己完成；任何报错你先自己排查修复（不改架构），
需要我做的事必须给我详细到"点哪里/输入什么"的步骤。

【0. 前置：只问我要一个密钥】
- 只问我要 OPENAI_API_KEY（全 OpenAI：STT+LLM+TTS，一个 key 跑通；若我不会拿，按 USER_TODO.md 指引我）。
- 其它一律不要问我账号；LiveKit 用本地 Docker 起，通知用本地 Dashboard。

【1. 安装依赖】
- python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
- mkdir -p data
- 预下载语音模型：PYTHONPATH=src python -m visitor_agent.agent download-files

【2. 本地起 LiveKit（不需要我的账号）】
- 检查 Docker 是否安装；没有就帮我装（或告诉我一条安装命令）。
- 起本地 dev 版 LiveKit：
  docker run -d --name livekit-dev -p 7880:7880 -p 7881:7881 -p 7882:7882/udp livekit/livekit-server --dev
  （--dev 自带固定密钥：api key=devkey，secret=secret，地址 ws://localhost:7880）

【3. 写 .env】
- cp .env.example .env，然后写入：
  OPENAI_API_KEY=<我给的>
  LLM_PROVIDER=openai           # 全 OpenAI，一个 key 跑通
  LLM_MODEL=gpt-4o-mini
  LIVEKIT_URL=ws://localhost:7880
  LIVEKIT_API_KEY=devkey
  LIVEKIT_API_SECRET=secret
  NOTIFY_CHANNEL=none           # 保安在 Dashboard 上点放行，无需任何账号
  PUBLIC_BASE_URL=http://localhost:8080

【4. 起两个进程】
- 终端A：source .venv/bin/activate && PYTHONPATH=src python -m visitor_agent.web.server
- 终端B：source .venv/bin/activate && PYTHONPATH=src python -m visitor_agent.agent dev
  确认 worker 显示已连接 LiveKit（registered）。

【5. 让我体验测试（你给我可点链接 + 操作说明）】
- 给我两个链接：
  · 访客端  http://localhost:8080/voice
  · 后台端  http://localhost:8080/dashboard
- 告诉我操作：在 /voice 点"接入门卫"、允许麦克风，AI 会先开口问"车牌、找哪家、什么事"，
  我对着麦克风回答（可以一句话说多项）。同时我盯着 /dashboard 看实时字幕和采集字段。
- 信息齐了，Dashboard 右侧"访客记录"会出现这条、状态"待确认"，我点"✅放行"，
  状态变"已放行"、出现"抬杆"事件。请确认这条链路在我这边真的发生了。
- 帮我留意：从 AI 开口到访客记录出现是否 ≤ 25 秒。

【6. 顺便验证加分项】
- 回访识别：用同一车牌再登记一次，开场 AI 应识别为回访、直接确认不重问。
- 门卫查询：PYTHONPATH=src python -m visitor_agent.guard_query "今天一共多少访问车辆？"

【7. 跑测试自检】
- PYTHONPATH=src python -m pytest -q  应全部通过。

【输出要求】
- 每步做完简短报结果；最后给我：访客链接、后台链接、我要点的按钮、端到端耗时。
- 我只负责体验和提意见，所以请把"该我点的地方"写得非常清楚。
```

---

## 其它版本

- **手机扫码版**：见 **[QR_DEMO.md](QR_DEMO.md)**（已做好，明天即可测；路 A 用 LiveKit Cloud 免费账号，路 B 同一 WiFi 零账号）。
- **真实电话**：接 Twilio 号码 → LiveKit SIP（需要你的 Twilio 账号，按 SETUP_CHECKLIST.md 第 5 步）。
- **外部通知**：想让通知发到手机群，把 `NOTIFY_CHANNEL` 改 `discord` 并填 webhook（见 USER_TODO.md 可选部分）。

> 一句话：现在这版**只要一个 OpenAI key 就能在你电脑上点开网页和 AI 说话、后台点放行**，其余全自动。
