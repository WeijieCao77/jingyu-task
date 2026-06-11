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

### v0.11 — 转人工 / 保安介入（回答"扫码场景能否转人工"）
- **改动**：因三种接入共用同一 LiveKit 房间，实现"真人介入"——
  - `request_human` 工具（LLM 在访客要求/听不懂/异常时调用）+ prompt 转人工规则；发 `escalation` 事件。
  - Dashboard 实时流高亮 ⚠️ 转人工 + 一键 **📞 介入通话** 按钮；新增保安介入页 `/guard_call`（接入访客房间、开麦）。
  - 保安加入（identity=guard）时 **AI 自动让位**（say 一句后 `session.aclose()` 退出房间），保安与访客直接对讲；电话场景同理（LiveKit 支持 SIP 转接）。
  - 修一个真 bug：escalation payload 的 `reason` 被 `info.to_dict()` 的来访事由覆盖（合并顺序）。测试 37→39。
- **计划变更**：产品决策点 #4（异常兜底/转人工）从"待定"变为"v1 已做"；待用户定触发策略松紧与黑白名单。
- **未验证**：保安加入→AI 退出的实时表现需本地真跑确认（已记入 SMOKE_CHECK 思路）。

### v0.12 — 远程访问文档 + 产品决策记录
- **改动**：新增 **`REMOTE_ACCESS.md`**——在外用手机测试/操作家里常开电脑的方案（Tailscale 私有组网）：含①你亲手做的几步（手机装 Tailscale+登录、电脑授权、装 SSH App）②给本地 Claude Code 的全自动 prompt（装 Tailscale、改 LiveKit/web 绑 Tailscale 地址让手机能连语音、tmux 常驻会话供手机 SSH 驱动 Claude Code）。DOCS.md 已收录。
- **产品决策记录**：
  - **语音保持纯中文**：`STT_LANGUAGE=zh` 锁定中文识别，不开自动语种识别；prompt 全中文、TTS 说中文。（用户决定，当前默认即如此，无需改码。）
  - **转人工两模式确认**：① 管理员主动介入（每通来电可一键介入）② 客户要求转人工；都不触发则默认 AI。（已实现，见 v0.11 + PRODUCT_FLOW §5.5。）

### v0.13 — 采纳本地真跑（Windows 11 ARM64）反馈，修跨平台 bug
> 来源：用户在真实 Windows 机器上跑通并提交 `LOCAL_RUN_ISSUES.md`，定位多个真实问题。
- **P0-3（跨平台必修）**：`agent.py` 顶层预注册默认插件（openai/silero/anthropic）。Windows 用 spawn 起 job 子进程，providers 的惰性 import 落在工作线程 → `Plugins must be registered on the main thread` 崩溃、AI 完全不出声。顶层 import 在主线程注册解决。
- **P1-1（Windows 时区）**：`requirements.txt` 加 `tzdata; sys_platform=="win32"`，否则 `zoneinfo("Asia/Shanghai")` 在 Windows 抛错（4 测试失败 + 运行时 entry_time 崩）。
- **P1-2（turn-detector 依赖）**：钉 `transformers>=4.40,<5`、`huggingface_hub>=0.23,<1`（5.x/1.x 破坏 turn-detector 模型加载）；dry-run 验证解析无冲突。
- **P1-3（挂断按钮）**：`/voice` 与 `/guard_call` 加红色「挂断」按钮（`room.disconnect()`），不再只能关标签页。
- **P2-3（单 OpenAI key 跑仿真器）**：`sim/run_text.py` 改为尊重 `LLM_PROVIDER`——OpenAI 时走 Chat Completions tool-use 循环，名副其实"单 key 跑全部"。
- **文档**：SMOKE_CHECK 新增 §C5 Windows 专用备注（x64 Python / 非 Docker LiveKit 二进制 / PowerShell 命令 / dev 房间坑）；修 `37→39 passed`；README 加 Windows 指引。
- 测试仍 **39 passed**。
- **计划变更**：确立"跨平台（含 Windows ARM64）首跑可用"为交付门槛；turn-detector 仍保留 VAD 优雅降级。

### v0.14 — 远程访问文档纠偏：手机操作本地 Claude Code 为主
- **改动**：用户澄清核心需求是"在外面用手机**操作本地 Claude Code**（对话、改本地文件、调环境）"，而不只是测 app。重写 `REMOTE_ACCESS.md` 为"两个需求两条路"：
  - **需求 A（操作本地 Claude Code）**：推荐 **VS Code Tunnel**（Windows 原生、手机浏览器 vscode.dev、终端里 `claude` 即对话 + 文件编辑），无需 Tailscale；备选 SSH+tmux。各附给本地 CC 的 prompt。
  - **需求 B（测语音 app）**：保留 Tailscale 方案（让手机连本地 LiveKit 实时音频）。
  - 说明两条路可同时用（一个标签指挥 Claude Code、一个标签测语音）。
- **计划变更**：远程访问的主线从"手机测 app"修正为"手机操作本地 Claude Code"。

### v0.15 — 全云端部署（彻底甩掉家里电脑）
- **改动**：用户要求完全不依赖本地电脑、手机随处测。加云部署产物：
  - `Dockerfile`（容器内跑 web+agent）、`scripts/start.sh`（agent worker 后台 + web 前台）、`.dockerignore`、`fly.toml`。
  - `web/server.py` 适配云平台端口（`$PORT`）；`requirements.txt` 加 `psycopg2-binary`（Neon Postgres 驱动）。
  - **`DEPLOY.md`**：全云端方案（Railway/Fly + LiveKit Cloud + Neon + OpenAI），手机直连 LiveKit Cloud、容器只开 HTTP、无需 Tailscale/UDP；含账号清单、Railway 步骤、Fly 步骤、可交给 cowork/云端 CC 的部署 prompt、验收清单。
- **计划变更**：明确两条远程路线分工——**DEPLOY.md=全云端（无家用电脑）**；**REMOTE_ACCESS.md=远程操作家里电脑**。Serverless 边界落地为"web+agent 常驻云主机 + LiveKit Cloud + Neon"。

### v0.16 — 回到产品：AI 确认层 / 提速 / 门卫界面简化 / 美化 / 微信预备
> 来源：用户真机测试发现的产品问题。
- **AI 确认层（修语音识别错号码）**：prompt 要求在 complete 前**复述车牌+手机号让访客确认**（车牌逐位、手机号分组念），错了就改再复述。号码听错也能被访客当场纠正。
- **提速**：开启 LiveKit `preemptive_generation`（抢先生成）+ 调低 VAD 端点静音(0.4s) + `min_endpointing_delay`(0.4s)；均 env 可调（`PREEMPTIVE_GENERATION`/`VAD_MIN_SILENCE`/`MIN_ENDPOINTING_DELAY`）。
- **门卫界面简化**：Dashboard 砍掉实时对话流，只留**访客信息表格 + 放行按钮**（车牌/单位/事由/手机/姓名/时间/状态）；顶部只在"有来电/需转人工"时弹一条带「介入」按钮的提醒。完整对话仍存库（`call_events`），只是不再一直显示给门卫。
- **UI 美化**：访客 `/voice` 重做（渐变背景、动效语音球、友好文案、接通/挂断状态）；门卫页改清爽卡片表格。
- **微信预备方案 `WECHAT_PLAN.md`**：3 天内落地路径——方案 A 群机器人+链接放行（代码已具备，填 env 即用）/ 方案 B 自建应用模板卡片按钮回调。不急着实现，文档先行。
- 测试 39 passed（更新 voice 文案断言）。
- **计划变更**：从"基础设施/远程访问"切回"产品打磨"；号码准确性用 AI 确认层兜底而非强求模型。

### v0.17 — 通知渠道：Telegram + 企业微信多渠道（已并入主分支）
- **改动**（原 `feature/wechat-push`，PR #2 已合并）：
  - 通知做成**可同时多渠道**：`NOTIFY_CHANNEL` 逗号分隔（如 `telegram,wecom` 同时推两边）；`dispatch.push` 对每个渠道都发、任一成功即算成功。
  - 通知卡片（Telegram/企微/Discord）加入**姓名**字段。
  - **`NOTIFY_SETUP.md`**：5 分钟把消息推到手机（Telegram 首选）+ 企微/Discord + 给本地 CC 的设置 prompt。
  - 渠道路线图：**Telegram + 企业微信群机器人同步推进**（都只要手机号、不要公司/执照）；企微自建应用/微信为国内生产最终落地。`WECHAT_PLAN.md` 补"零、你需要准备什么（不需要营业执照）"。
- **计划变更**：通知主线定为 Telegram（demo 即用）；企业微信预备方案（群机器人已具备、自建应用按钮回调后续推进）；最终国内落地用国内软件。

### v0.18 —（分支 feature/data-matching）公司名单匹配 + 车牌省份归一
> 真机测试：车牌"粤A"记成"月月"、"蓝色鲸鱼"记成"蓝色金鱼"。
- **改动**：`roster.py` 公司名单模糊匹配（汉字+拼音相似度，"蓝色金鱼"→"蓝色鲸鱼科技"），接入登记流程、AI 确认纠正名；`slots.normalize_plate` 省份名→简称（广东A→粤A，31 省）。**默认关闭**（`ROSTER_PATH` 配了才生效）。`DATA_MATCHING_PLAN.md`。
- **计划变更**：数据准确性策略——封闭集合（公司）用名单匹配、开放集合（车牌/手机）用 AI 复述确认。

### v0.19 —（分支 feature/realtime-voice）语音架构 A/B：三段 pipeline → speech-to-speech (gpt-realtime)
> 真机感觉"说一句话/AI 说话会卡一会"——主因是 pipeline 三段串联。
- **改动**：**不换框架（仍 LiveKit）**，加 `VOICE_MODE` 开关：`pipeline`（默认）/ `realtime`。realtime 用 `openai.realtime.RealtimeModel`(`gpt-realtime`，同一 OpenAI key)，音频进音频出、**延迟明显更低**，且**仍保留 zh 文字转写 + 工具调用**——填槽/后台/数据库/转人工全不变。`ARCHITECTURE_AB.md` 对比两模式 + 提速/提准杠杆。
- **计划变更**：**架构演进的关键一步**——把"大脑"从三段 pipeline 切到 speech-to-speech，解决延迟；保留 pipeline 作可回退默认；最终用哪种由真机 A/B + 客户定。

### v0.20 — 模型可换架构（客户最终决定用哪个模型）
- **改动**：LLM 增加 `LLM_BASE_URL`——指向任一 **OpenAI 兼容端点**即可接 GPT/Claude/Gemini/Qwen/Llama/DeepSeek/豆包/Kimi 等**任意模型（含国内）**，工具调用照常；`providers.build_llm` 透传 base_url，留空=官方 OpenAI。
- **`MODELS.md`**：现在用哪些模型、怎么逐项换（LLM/STT/TTS/语音架构）、客户可选任意模型的配置矩阵、加新 provider 的方式。`.env.example` 加 `LLM_BASE_URL` 示例。
- **计划变更**：明确"模型是配置项不是架构"——客户选定后改 `.env` 三五行即切换，无需改码。

---

## 待办 / 下一步候选（计划池）
- [ ] 真机电话端到端联调 + 25 秒计时（Twilio SIP，用户本机）
- [ ] 中文音色 A/B：OpenAI TTS vs MiniMax / Azure zh-CN / Qwen3-TTS
- [ ] 架构 A/B：TEN Framework / Pipecat 对照
- [ ] 企微自建应用模板卡片（按钮回调）作为生产形态
- [ ] Serverless 部署样例（Cloudflare Workers 跑 /confirm + Neon）
- [ ] 海康 ISAPI 真实抬杆对接（园区内网）
