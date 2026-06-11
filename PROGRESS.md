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

## 第四轮（把"需要用户做的"压到最小 + 全自动 + 教程）

- ✅ **保安通知默认 `none` = 后台 Dashboard 点"放行"**：访客记录每条待确认显示绿色"✅放行"按钮 →
  `POST /api/confirm/{id}` → 抬杆 + 记事件。**零账号**，不再需要 Discord/企微。Discord/Telegram 仍可选。
- ✅ **LiveKit 改本地 Docker 自托管**（`livekit-server --dev`，devkey/secret）→ **不需要用户的 LiveKit 账号**。
- ✅ **`ACCEPTANCE_PROMPT.md` 全自动重写**：本地 Claude Code 负责装依赖/起 LiveKit/下载模型/配置/起服务/隧道；
  只问用户要 2 个 API key；并要求把"该用户点的地方"写清楚。
- ✅ **`USER_TODO.md`**：手把手图文教程——怎么拿 Anthropic / OpenAI key（注册→充值→建 key→复制）、
  怎么交给本地 CC、花费预期、可选 Discord/Telegram。
- ✅ 测试 24 → **26 全绿**（新增本地确认按钮 + notify=none）。
- 🎯 现在用户要做的全部 = 拿两个 API key 粘贴 + 体验测试。其余全自动、零额外账号。

## 第五轮（单 key 简化 + 扫码版做出来）

- ✅ **默认改为全 OpenAI（单 key）**：`LLM_PROVIDER=openai` / `LLM_MODEL=gpt-4o-mini`，只需一个 `OPENAI_API_KEY` 跑通 STT+LLM+TTS。Anthropic（Claude 大脑）降级为可选升级。
- ✅ **门卫查询 Agent 改为 provider-aware**：OpenAI / Anthropic 双驱动，单 key 下加分项不再报错。
- ✅ **扫码版做出来（明天可测）**：`QR_DEMO.md` 两条路（路 A=LiveKit Cloud 免费账号，任何网络；路 B=本地 LiveKit + 同一 WiFi，零账号），各含可直接喂本地 CC 的 prompt；`scripts/run_tunnel.sh`（cloudflared 免账号隧道）；`/voice` 手机端音频加固（playsinline + 手势 play）。
- ✅ **密钥/配置说明**：README 新增"🔐 密钥与配置（public 必读）"——密钥存 `.env`(gitignored)、别人 clone 后 `cp .env.example .env` 填自己的、单/双 key 选择；审计确认仓库无真实密钥泄漏。
- ✅ `USER_TODO.md` 重写：默认单 key（OpenAI）教程 + 扫码版 LiveKit Cloud 三个值教程 + 安全说明。
- ✅ 测试仍 **26 全绿**。
- 🎯 现在最简验收 = 一个 OpenAI key → 本地 CC 全自动 → 网页说话 + 后台放行；扫码版按 QR_DEMO.md。

## 第六轮（数据存储策略 + 全面回访识别）

- ✅ **数据存储讲清并加固**：`DATABASE_URL` 一行切换——本地 demo=SQLite 文件(重启不丢)，生产=Neon Postgres(持久/多机/容器不丢)。
  DESIGN 新增 §7.5 + 风险提示（临时容器用 SQLite 会丢数据→生产必须云库）；`.env.example` 加 Neon 示例。表 `create_all` 自动建。
- ✅ **回访识别升级为"识别画像"**：`repo.recognize(plate, phone)` 用"手机=人、车牌=车"的身份模型，返回 match_type/累计次数/姓名/上次单位事由。
  按场景分级措辞：同车同人=自信确认；换车(仅手机)=认出本人；换人(仅车牌)=认出车但不假设同一人；常客="第N次"；可选采集姓名(张师傅)。
  不盲目放行——把上次信息作为"一句话确认"抛回，说不一样就更新。
- ✅ 新增可选 `name` 字段（slots/Visit/工具/prompt 全链路）；`visits` 加 name 列。
- ✅ 测试 27 → **29 全绿**（新增 recognize 画像 4 场景 + 姓名可选）。

## 第七轮（更深优化 + 变更日志）

- ✅ **常客名单 / 访客画像**：`repo.visitor_profiles()` 按人(手机)聚合——来访次数、车牌集、常去单位、姓名、已放行次数、最近一次。
  管理后台 `/admin` + `/api/profiles`；门卫查询 Agent 新增 `frequent_visitors` 工具。
- ✅ **开闸时间单列**：Dashboard 访客记录新增"开闸时间"列（confirmed_at）。
- ✅ **新增 `CHANGELOG.md`**：记录每次版本改动 + 计划变更时间线（v0.1→v0.7 已补齐）+ 计划池。
- ✅ 测试 29 → **31 全绿**。

## 第八轮（自主夜间·用户睡觉）

- ✅ 自我代码审查修两个真实 bug：门卫查询 OpenAI 路径消息序列化；providers 传 `api_key=None` 隐患。
- ✅ SQLite WAL + busy_timeout（双进程并发健壮）。
- ✅ 海康抬杆双模式（stub 默认 / 配 `HIKVISION_URL` 走真实 ISAPI）+ 单测。
- ✅ 中文音色升级真代码：`STT=deepgram` / `TTS=azure(zh-CN)` 一行 env 切换（lazy import）。
- ✅ 测试 31 → **34 全绿**。决策与计划变更同步进 CHANGELOG v0.8。
- 说明：本轮只做离线可验证、不需你账号/钱的项；真机电话/真账号项留待你 review 后定。

## 第九轮（采纳真机测试反馈 + 两条新需求；v0.22）

用户在 Windows 11 ARM64 真机测完新版本，给了详细"问题→根因→方案"总结，并新增两条需求。本轮一次性落地（测试 49→**74** 离线全绿；2 个 `/token` 用例只差沙箱未装 livekit）：

- ✅ **realtime 合入主线（FR-1 + P0-4）**：`VOICE_MODE` 开关并入 dev，**不回退** roster/`LLM_BASE_URL`（realtime 分支是从二者合并前分出的，naive merge 会删掉它们）→ 手动只挪 realtime 增量。realtime + 名单/黑白名单**可同时用**（槽位逻辑与语音模式无关）。修复 realtime `session.say(固定文本)` 崩溃 → `_speak()`（realtime=`generate_reply`/pipeline=`say`），开场白 + 转人工让位都走它。
- ✅ **黑白名单（NEW-2）**：`access.py` 车牌/手机精确匹配，黑名单优先；黑名单告警+绝不自动放行、白名单可选 `AUTO_PASS_WHITELIST` 自动放行；`ACCESS_LIST_PATH` 开关，默认关。
- ✅ **通知加"老访客 + 黑白名单"信息（NEW-1）**：Telegram/企微/Discord 卡片高亮行 + 后台 ⛔/✅ 徽标（共享 `common.status_lines()`）。
- ✅ **放行后 AI 语音通知访客（FR-2）**：web→LiveKit 数据消息→agent `_speak`；`visits.room` + best-effort（挂断/未配 LiveKit 静默不影响放行）。
- ✅ **① Telegram localhost 按钮**：不带按钮+链接进正文+失败降级纯文本；`.env.example`/`NOTIFY_SETUP` 注明。
- ✅ **⑥ `/voice` 自动播放兜底**：「点击启用声音」按钮 + 提示。
- ✅ **② 测试隔离**：禁用该用例 `.env` 读取；`/token` 未配置=400 前置到 import livekit 之前。
- ✅ **DB 迁移**：`access_status`/`room` 列 + `_ensure_columns()` 增量加列（老 SQLite 不崩）。

决策：realtime 真机更快 → 提为主线可选模式（默认仍 pipeline，待客户定默认）；黑白名单从计划池提前实现。真机验证 prompt 见 `SESSION_HANDOFF.md`（realtime+名单同开、黑白名单、FR-2 放行播报）。

## 怎么快速验收（建议顺序）

1. `PYTHONPATH=src pytest -q` → 应 16 passed。
2. `./scripts/run_sim.sh --scenario scenarios/songhuo.json`（填好 Anthropic 密钥）→ 看对话质量。
3. 配企微 webhook + 隧道，`--live` 跑一遍 → 看微信卡片 + 确认放行。
4. 其余照 TEST_TASKS.md 交给本地 CC。
