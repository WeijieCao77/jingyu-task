# 🎬 验收用：一键起服务的 Prompt（复制给本地 Claude Code）

下载本仓库到本地后，**把下面整段**复制给你电脑上的 Claude Code。它会装好依赖、问你要密钥、起好服务，
并告诉你拨哪个号、打开哪个后台页面。然后你用手机拨号、和 AI 对话，在后台 Dashboard 看实时效果。

> 小贴士：如果你还没配 Twilio 电话号，先用文末的「无电话快速验收」也能完整看到对话 + 后台 + 放行。

---

```
你是我的本地运行助手。这个仓库是一个"园区语音访客登记 Voice Agent"。请帮我把它在本机跑起来，
让我能用手机拨打电话、和 AI 门卫对话，并在后台 Dashboard 实时看到对话、采集字段、企业微信推送与放行。
请一步步做，遇到需要密钥/账号的地方停下来问我，不要把任何密钥写进会被提交的文件。

【1. 安装】
- 在仓库根目录创建虚拟环境并安装依赖：
  python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
- mkdir -p data ；chmod +x scripts/*.sh

【2. 配置 .env】
- cp .env.example .env
- 问我并填入：ANTHROPIC_API_KEY、OPENAI_API_KEY、WECOM_WEBHOOK_URL（企业微信群机器人）。
  这三个有了就能验证「对话 + 微信推送 + 后台」。先不用 Twilio/LiveKit。

【3. 起后台 Dashboard + 确认服务】
- 后台运行：source .venv/bin/activate && PYTHONPATH=src python -m visitor_agent.web.server
- 打开 http://localhost:8080/dashboard ，让我能看到这个页面（这就是我要看的"后台"）。
- 用 ngrok 或 cloudflared 把 8080 映射到公网，拿到 https 地址，写回 .env 的 PUBLIC_BASE_URL，
  （保安点的"确认放行"链接需要公网可达）。然后重启 web 服务使其生效。

【4. 先做无电话验收（让我马上看到效果）】
- 运行：PYTHONPATH=src python -m visitor_agent.sim.run_text --scenario scenarios/songhuo.json --live
- 让我观察：①Dashboard 实时出现对话和采集字段 ②企业微信群收到访客卡片
  ③我点卡片里的"确认放行"链接 → 浏览器显示"已放行" → Dashboard 出现"保安确认/抬杆"，访客记录变"已放行"。
- 再让我自己交互聊一次：PYTHONPATH=src python -m visitor_agent.sim.run_text --live
  我会假装访客随便说，验证 AI 是否像真人门卫（批量提问、不机械、能补缺）。

【5. 接真实电话（Twilio + LiveKit）】
- 问我要 LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET，填进 .env。
- 启动语音 worker：source .venv/bin/activate && PYTHONPATH=src python -m visitor_agent.agent dev
  确认它显示已注册、等待来电。
- 按 SETUP_CHECKLIST.md 第 5 步，把我的 Twilio 号码经 SIP 接到 LiveKit
  （参考 https://docs.livekit.io/telephony/accepting-calls/inbound-twilio/ ，
  用 lk CLI 建 inbound trunk + dispatch rule）。需要我在 Twilio/LiveKit 控制台点什么，明确告诉我。
- 配好后告诉我拨打哪个号码。

【6. 现场模拟（我来操作）】
- 我用另一部手机拨打该号码，假装是来访客户。
- Agent 应先开口："您好，请问车牌号多少，今天找哪家公司，什么事儿？"
- 我和它对话报车牌/公司/事由/手机号。
- 你提醒我同时看着 http://localhost:8080/dashboard ：对话字幕、采集字段、推送、确认、抬杆都应实时出现，
  企业微信群也应收到卡片。用秒表测：从 Agent 开口到微信卡片出现是否 ≤ 25 秒。

【7. 顺手验证加分项】
- 回访识别：用同一车牌再跑一次 sim --live（或再拨一次电话），开场 AI 应识别为回访、直接确认而非重问。
- 门卫查询：PYTHONPATH=src python -m visitor_agent.guard_query "今天一共多少访问车辆？"
  和 "什么时间段访问最多？" —— 看回答数字是否正确。

【输出要求】
- 每一步做完简短告诉我结果；起好的服务给我可点的本地/公网链接。
- 任何报错先贴原文，再尝试最小修复并说明改了什么（不要改架构）。
- 全部跑通后，给我一句话总结：拨打号码、Dashboard 地址、企业微信效果、端到端耗时。
```

---

## 无电话快速验收（30 秒看到全貌）

如果暂时不想配 Twilio，只做第 1–4 步即可：填 3 个密钥 → 起 web → 打开 `/dashboard` → 跑 `sim --live`，
你就能在后台看到「实时对话 + 采集字段 + 企微卡片 + 确认放行 + 抬杆」整条链路。电话只是把"打字"换成"说话"。
