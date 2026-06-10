# 夜间执行日志（决策 + 卡点，供你审查）

日期：2026-06-10（美东夜间）。本轮目标：在你睡觉时一口气交付 v1 + 加分项。

## 本轮做了什么

- ✅ 市场调研（5 个并行子代理，带 source）→ 确定架构：Pipeline + LiveKit + Twilio + 企微 webhook（详见 DESIGN.md）。
- ✅ 完整可运行代码：
  - 对话核心 `prompts.py` / `slots.py` / `session_logic.py`（live & sim 共用，单一事实源）
  - LiveKit worker `agent.py` + provider 装配 `providers.py`（STT/LLM/TTS 全 env 切换）
  - 企微推送 `notify/wecom.py` + 抬杆 stub `notify/gate.py`（含 ISAPI 真实形态）
  - 数据层 `db/`（SQLite/Neon 通用）+ 确认服务 `web/server.py`（/confirm + /guard/query）
- ✅ 加分项：回访识别、门卫查询 Agent、并发（每会话隔离）、Serverless 诚实分层文档。
- ✅ 离线文本仿真器 `sim/run_text.py`（无电话/只需 Anthropic 密钥即可验证对话）。
- ✅ 16 个离线单测，**全绿**（`PYTHONPATH=src pytest -q`）。
- ✅ 文档：README（一页+mermaid）、DESIGN（选型+证据+延迟预算+中国路径+serverless）、SETUP_CHECKLIST、TEST_TASKS（本地 CC 验证 prompt）、DEMO_SCRIPT。

## 关键决策（及理由）

1. **Pipeline 而非 s2s**：业务必须拿到文本做填槽/发微信/查询，s2s 返回音频需额外转写。详见 DESIGN §1。
2. **LLM = Claude Haiku 4.5，关 thinking**：voice 场景最低延迟、中文+工具调用够用、最省。
3. **v1 STT/TTS 用 OpenAI**：因为你当前只有 OpenAI+Anthropic 两个账号；全部 env 可切，中文音色升级路径（MiniMax/Azure/Qwen3-TTS）已留好。
4. **保安确认用 token 链接**而非按钮回调：群机器人是单向推送，链接是最稳的 demo 方案；生产可升级企微自建应用模板卡片。
5. **抬杆 stub**：控制器在园区内网，笔记本无法直连；真实 ISAPI 调用形态写进代码作活文档。
6. **门卫查询用参数化工具而非裸 text-to-SQL**：防注入、更可控。

## 卡点 / 已按推荐方案处理

- **[已修复] 车牌规范化漏了中文间隔号 `·`**：单测 `test_normalize_plate("苏E·9F8K7")` 暴露——口语车牌常带 `·`。已把清洗正则扩展为 `[\s\.\-·•‧・]`，重跑全绿。
- **[已处理] FastAPI `on_event` 弃用警告**：改为 `lifespan` 上下文管理器。
- **[环境限制，非代码问题] 无法在本远程环境做真实联调**：出网白名单挡住 OpenAI/Twilio，且无音频/电话硬件。因此：
  - 代码已用"安装后 introspect 真实 API 签名"保证正确（LiveKit 1.5.17、anthropic 0.109、openai 2.41 均已核对）；
  - 真实电话 + 密钥联调写成 `TEST_TASKS.md`，交给你本机 Claude Code 跑。
- **[已知第三方告警，无影响]** starlette TestClient 与 httpx 的 deprecation 警告，不影响功能。

## 尚未做 / 下一步建议（等你 review 后定）

- [ ] 真实电话端到端联调 + 25 秒计时（你本机，TEST_TASKS 任务 5）。
- [ ] 中文音色 A/B：v1 是 OpenAI TTS，建议接 MiniMax 或 Azure zh-CN 对比自然度。
- [ ] 架构 A/B（你提过要测其他架构）：可对照 TEN Framework（中文 turn detection）或 Pipecat。
- [ ] 企微自建应用模板卡片（带按钮回调）替代 token 链接，作为生产形态。
- [ ] Serverless 部署样例（Cloudflare Workers 跑 /confirm + Neon），音频层仍需常驻进程。
- [ ] 海康 ISAPI 真实对接（需进园区内网）。

## 第二轮（你授权 GitHub + 明确验收体验后）

- ✅ 建 `main` 基础分支（git plumbing 空初始提交 + rebase feature），开 **draft PR #1**，历史干净可合并。
- ✅ **实时后台 Dashboard**（`/dashboard`）：SSE 流式显示通话时间线（对话字幕/采集字段/推送/确认/抬杆）+ 访客记录表。
  - 新增 `call_events` 表 + `repo.log_event/events_after`；agent 注册 `conversation_item_added` 写字幕（防御式，绝不影响通话）；`RegistrationSession` 加 `event_sink` 发槽位/完成事件；确认端点发 confirmed/gate 事件；`sim --live` 也喂 Dashboard。
- ✅ **`ACCEPTANCE_PROMPT.md`**：一段可直接喂本地 Claude Code 的开机即用 prompt——装依赖→问密钥→起 web+dashboard→`sim --live` 无电话验收→接 Twilio/LiveKit→拨号现场模拟，并含"无电话 30 秒快速验收"。
- ✅ 测试从 16 → **19 全绿**（新增 dashboard/event/confirm-event 测试）。
- 🔔 已设每小时自检心跳，订阅了 PR 活动（仓库暂无 CI workflow，无 CI 可跑；无待处理评论）。

## 第三轮（聚焦"下载即用 + 美国可用"）

- ✅ **浏览器麦克风语音** `/voice` + token 端点：只需 LiveKit + 两个密钥，开网页点按钮就能对着麦克风和 AI 对话，无需 Twilio。
- ✅ **扫码即用** `/qr`：入口贴二维码，访客手机扫 → 打开 /voice 对话（对应"扫个码就能完成"）。
- ✅ **保安通知改为可插拔渠道**：`NOTIFY_CHANNEL` = discord(默认) / telegram / wecom。demo 用 **Discord Webhook**（美国可用、一个 URL），Telegram 带确认按钮，企业微信留作生产。`notify/{common,dispatch,discord,telegram,wecom}.py`。
- ✅ **turn detector 容错**：模型缺失时自动降级为 VAD-only，不让通话崩（"下载即用"优先）。
- ✅ 文档同步：ACCEPTANCE_PROMPT 改为 Discord + 浏览器语音为主线、电话为精修；README/DESIGN/SETUP 同步；DESIGN 新增 §5 渠道适配器 + §5.5 访客三形态。
- ✅ 测试 19 → **24 全绿**（新增 voice/token/qr/discord/telegram）。
- 📌 路线：电话(Twilio SIP)版作为下一步精修；三种接入最终汇入同一 LiveKit room + 同一 Agent。

## 怎么快速验收（建议顺序）

1. `PYTHONPATH=src pytest -q` → 应 16 passed。
2. `./scripts/run_sim.sh --scenario scenarios/songhuo.json`（填好 Anthropic 密钥）→ 看对话质量。
3. 配企微 webhook + 隧道，`--live` 跑一遍 → 看微信卡片 + 确认放行。
4. 其余照 TEST_TASKS.md 交给本地 CC。
