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

## 怎么快速验收（建议顺序）

1. `PYTHONPATH=src pytest -q` → 应 16 passed。
2. `./scripts/run_sim.sh --scenario scenarios/songhuo.json`（填好 Anthropic 密钥）→ 看对话质量。
3. 配企微 webhook + 隧道，`--live` 跑一遍 → 看微信卡片 + 确认放行。
4. 其余照 TEST_TASKS.md 交给本地 CC。
