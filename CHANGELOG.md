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

### v0.8 — 自主夜间：代码审查修复 + 生产就绪 + 健壮性（用户睡觉，自行决定）
- **改动**：
  - 自我代码审查（medium）发现并修两个真实 bug：① 门卫查询 OpenAI 路径把原始 SDK message 对象塞回 messages（可能带 null 字段被 API 拒）→ 改为干净 dict；② providers 给插件传 `api_key=None` 的隐患 → 改为仅在非空时传。
  - **并发健壮性**：SQLite 开启 WAL + busy_timeout，agent(写) 与 web(读/写) 同文件并发不再 "database is locked"。
  - **生产就绪**：海康抬杆 `notify/gate.py` 双模式——默认 stub，配 `HIKVISION_URL` 即走真实 ISAPI（digest auth PUT），含单测（mock）。
  - **中文音色升级路径落成真代码**：providers 增加 `STT=deepgram`、`TTS=azure(zh-CN)` 分支（lazy import + 一行 env 切换，文档标注需装对应插件）。
  - 测试 31 → 34。
- **计划变更**：用户睡前授权"自行决定并记录"。本轮聚焦离线可验证、不需用户账号/钱的高价值项（健壮性/生产就绪/选型可切换），不碰需真机/真账号的项。

### v0.9 — 全项目审查 + 框架调研报告 + 一页 README（用户要求）
- **改动**：
  - **审查修复**：发现并修关键启动 bug——LiveKit worker 从 `os.environ` 读凭据而 `.env` 不自动导出 → agent/web 启动时 `load_dotenv()`。没有这个修复 `agent dev` 大概率连不上。
  - **`FRAMEWORK_RESEARCH.md`**：三路并行调研（开源框架/SaaS/电话原生云栈）汇成正式选型报告——为什么用 LiveKit、各竞品优势、为什么不用（Pipecat 无原生 SIP+GIL 单容器单通话；TEN 中文最强但 7 天风险高；Vapi/Retell 锁定+把被考察的能力外包；Nova Sonic 无中文；阿里/火山应作为插件而非替代）。含决策矩阵与 LiveKit 已知弱点+对策。
  - **README 压成一页**（任务硬性要求"一页以内"）：只留架构图+部署+env，长内容移至各专门文档。
  - **`SMOKE_CHECK.md`**：首次真跑排查清单（症状→原因→处置 + 验收断言 + 已知未验证项）。
- **计划变更**：经全项目对照任务原文审查，明确两点风险供用户决策——① demo 主线（浏览器+Dashboard）与任务字面（电话+微信）存在偏移，提交前需补真实电话+通知演示或在答辩讲清 trade-off；② 端到端语音链路在沙箱中无法真跑，"能用"需用户本地一次真跑来证实（SMOKE_CHECK 已备好）。

### v0.10 — 文档归档与汇总（用户要求）
- **改动**：把散在对话里的分析全部沉淀为文档并归类——
  - **`PRODUCT_FLOW.md`**：产品全流程 + 访客/管理者双视角（含实际页面文字与卡片内容）+ PM 待拍板 8 点。
  - **`DOCS.md`**：全部文档分类索引（产品/选型/部署验收/开发记录 四类 + 用途/读者/一句话 + 按角色阅读建议 + 代码导航）。
  - README 顶部加文档索引入口。
- **计划变更**：确立文档体系——快速了解三篇（README/PRODUCT_FLOW/FRAMEWORK_RESEARCH），其余按四类归档，DOCS.md 为统一入口。

---

## 待办 / 下一步候选（计划池）
- [ ] 真机电话端到端联调 + 25 秒计时（Twilio SIP，用户本机）
- [ ] 中文音色 A/B：OpenAI TTS vs MiniMax / Azure zh-CN / Qwen3-TTS
- [ ] 架构 A/B：TEN Framework / Pipecat 对照
- [ ] 企微自建应用模板卡片（按钮回调）作为生产形态
- [ ] Serverless 部署样例（Cloudflare Workers 跑 /confirm + Neon）
- [ ] 海康 ISAPI 真实抬杆对接（园区内网）
