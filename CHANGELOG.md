# 变更日志 CHANGELOG

记录每一次**版本改动**与**计划变更**的时间线。
（`PROGRESS.md` 记决策/卡点细节；本文件记"改了什么 + 计划怎么变"。日期为美东。）

格式：`改动` = 代码/功能变化；`计划变更` = 方向/范围/决策的调整。

---

## 2026-06-10

### v0.1 — 初版骨架（市场调研后定架构）
- **改动**：搭出完整可运行 v1——LiveKit 电话 worker、STT/LLM/TTS env 可切装配、中文门卫对话核心、
  企微推送 + 确认服务 + 抬杆 stub、SQLite 数据层、离线文本仿真器、16 个单测。文档 README/DESIGN/SETUP/TEST_TASKS/PROGRESS/DEMO_SCRIPT。
- **计划变更**：经 5 路并行调研定调 **Pipeline（非 s2s）+ LiveKit + Twilio + 企微**；加分项先留接口、基础闭环优先。

### v0.2 — 建 main + draft PR + 实时 Dashboard
- **改动**：建 `main` 基础分支（空初始提交 + rebase），开 **draft PR #1**；新增实时后台 Dashboard（`/dashboard`，SSE 通话时间线 + 访客记录）；`call_events` 表。测试 16→19。
- **计划变更**：明确"产品成品工作流"与交付物；引入"本地 Claude Code 测试 + 夜间执行"协作节奏。

### v0.3 — 浏览器语音 + 扫码 + 通知渠道可插拔
- **改动**：浏览器麦克风语音页 `/voice` + LiveKit token 端点；扫码页 `/qr`；通知做成适配器（Discord/Telegram/企微，`notify/dispatch.py`）；turn detector 容错降级。测试 19→24。
- **计划变更**：**通知渠道从"绑死企业微信"改为可插拔**，demo 用美国可用渠道；访客接入定为"浏览器/扫码/电话"三形态，电话作为精修。

### v0.4 — 把"用户要做的"压到最小
- **改动**：保安通知默认 `none`=后台 Dashboard 点"放行"（`/api/confirm/{id}`）；LiveKit 改本地 Docker `--dev` 自托管；`ACCEPTANCE_PROMPT.md` 全自动重写；`USER_TODO.md` 图文教程。测试 24→26。
- **计划变更**：确立原则 **"除了花钱和账号，其余全由本地 CC 完成"**；用户只体验测试。

### v0.5 — 单 key 简化 + 扫码版做出来
- **改动**：默认全 OpenAI（`LLM_PROVIDER=openai`/`gpt-4o-mini`），一个 key 跑通；门卫查询 Agent 改 provider-aware；
  扫码版 `QR_DEMO.md`（路 A=LiveKit Cloud 免费号；路 B=同 WiFi 零账号）+ `scripts/run_tunnel.sh` + `/voice` 手机端音频加固；
  README 新增"🔐 密钥与配置"。测试保持 26。
- **计划变更**：**先用一个 API key 把线路跑通**（用户决定，简单优先）；扫码版从"精修"提前为"明天可测"。

### v0.6 — 存储策略 + 全面回访识别
- **改动**：`DATABASE_URL` 本地 SQLite / 云 Neon 切换文档化（DESIGN §7.5 + 风险提示）；
  回访识别升级为 `repo.recognize()` 识别画像（手机=人/车牌=车，match_type + 累计次数 + 姓名 + 上次信息），按场景分级措辞；新增可选 `name` 字段全链路。测试 27→29。
- **计划变更**：回访识别从"查一条"改为"按真实使用场景的画像识别"；明确"数据都要保存、生产上云库"。

### v0.7 — 访客画像聚合 + 开闸时间 + 变更日志
- **改动**：`repo.visitor_profiles()` 常客名单聚合（按人）；管理后台 `/admin` + `/api/profiles`；门卫查询新增 `frequent_visitors` 工具；
  Dashboard 访客记录新增"**开闸时间**"列；新增本 `CHANGELOG.md`。测试 29→31。
- **计划变更**：执行"更深优化"（常客画像 + 开闸时间单列）；引入版本/计划变更日志。

---

## 待办 / 下一步候选（计划池）
- [ ] 真机电话端到端联调 + 25 秒计时（Twilio SIP，用户本机）
- [ ] 中文音色 A/B：OpenAI TTS vs MiniMax / Azure zh-CN / Qwen3-TTS
- [ ] 架构 A/B：TEN Framework / Pipecat 对照
- [ ] 企微自建应用模板卡片（按钮回调）作为生产形态
- [ ] Serverless 部署样例（Cloudflare Workers 跑 /confirm + Neon）
- [ ] 海康 ISAPI 真实抬杆对接（园区内网）
