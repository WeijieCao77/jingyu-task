# 部署清单（你早上照着做即可联调）

按顺序勾选。前 3 步无需电话即可验证对话；4–6 步接通真实电话。

## ✅ 0. 本地装好

```bash
cd jingyu-task
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
mkdir -p data
chmod +x scripts/*.sh
```

## ✅ 1. 填两个 LLM 密钥（最先能验证对话）

`.env` 里：
- `ANTHROPIC_API_KEY=` → https://console.anthropic.com 拿
- `OPENAI_API_KEY=` → https://platform.openai.com 拿

**立即验证对话逻辑（无需电话）：**
```bash
./scripts/run_sim.sh --scenario scenarios/songhuo.json
./scripts/run_sim.sh --scenario scenarios/mianshi.json
./scripts/run_sim.sh                      # 自己随便聊，测"像不像真人"
```
看：是否一句话同时问多项、是否不重复追问、3 轮内完成、复述自然。

## ✅ 2. 保安通知渠道（demo 默认 Discord，无需企业微信）

1. Discord：随便建个频道 → 频道设置 → 整合 → Webhook → 新建 → 复制 URL。
2. `.env` 里：`NOTIFY_CHANNEL=discord`，`DISCORD_WEBHOOK_URL=<刚复制的 URL>`。
   （想用 Telegram：`NOTIFY_CHANNEL=telegram` + `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`；
    生产用企业微信：`NOTIFY_CHANNEL=wecom` + `WECOM_WEBHOOK_URL`。）
3. 验证推送（live 仿真会真发到频道）：
   ```bash
   ./scripts/run_sim.sh --scenario scenarios/songhuo.json --live
   ```
   频道里应收到访客卡片 + "✅确认放行"链接。

## ✅ 3. 起确认服务 + 公网隧道

```bash
./scripts/run_web.sh           # 终端A：本地 :8080
# 终端B：把 8080 映射到公网（任选）
ngrok http 8080                # 或 cloudflared tunnel --url http://localhost:8080
```
把隧道给出的 https 地址填进 `.env` 的 `PUBLIC_BASE_URL=`，重跑第 2 步的 `--live`，**手机点群里链接**应看到"已放行 ✓"，web 终端打印 `[GATE] 已发送抬杆指令`。

> 至此：对话 + 微信 + 确认 + 抬杆 全链路（除电话）已闭环。

## ✅ 4. LiveKit 凭据

1. https://cloud.livekit.io 建 project，拿 `LIVEKIT_URL` / `API_KEY` / `API_SECRET` 填进 `.env`。
2. 起 worker：`./scripts/run_agent.sh dev`（应显示 registered / 等待来电）。

## ✅ 5. Twilio 号码 → LiveKit SIP

1. https://twilio.com 注册，买一个语音号码（美国号，$1/月）。
2. 在 LiveKit 建 **inbound SIP trunk + dispatch rule**（指向 agent）：
   参考 https://docs.livekit.io/telephony/accepting-calls/inbound-twilio/
   （LiveKit CLI：`lk sip inbound create` / `lk sip dispatch create`）。
3. 在 Twilio 号码的 Voice 配置里，把来电转到 LiveKit 给的 SIP URI / Origination。

## ✅ 6. 真机拨打测试

用另一部手机拨打 Twilio 号码：
- Agent 应开口："您好，请问车牌号多少，今天找哪家公司，什么事儿？"
- 自然回答 → 群里收到卡片 → 点链接 → 已放行。
- **计时**：从 Agent 开口到群消息出现，应 ≤ 25 秒。

录 1–2 分钟全流程视频（见 `DEMO_SCRIPT.md`）。

## 🧪 加分项验证

```bash
# 门卫查询 Agent（先用 --live 仿真造几条数据，再问）
python -m visitor_agent.guard_query "今天一共多少访问车辆？"
python -m visitor_agent.guard_query "什么时间段访问最多？"
# 回访识别：用同一车牌跑两次 --live 仿真，第二次开场应直接确认而非重问
```

## 常见坑
- 群里没收到卡片：检查 `WECOM_WEBHOOK_URL`，或看终端是否打印 webhook 错误码。
- 链接点了没反应：`PUBLIC_BASE_URL` 必须是**公网 https**（隧道），不能是 localhost。
- 中文音色机械：把 `TTS_MODEL/TTS_VOICE` 换 MiniMax 或 Azure zh-CN（见 DESIGN.md §4）。
- 电话接不通：先确认 `run_agent.sh` 显示已注册，再查 Twilio→LiveKit 的 SIP origination。
