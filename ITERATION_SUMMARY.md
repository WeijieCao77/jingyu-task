# 迭代与需求总结（供检查）

> 一份"全局账本"：**架构演进** + **你提出的每一条改进需求/方案变化** + **版本时间线** + **分支/PR 状态**。
> 细粒度的逐版本记录见 `CHANGELOG.md`；逐轮决策/卡点见 `PROGRESS.md`；本文是给人看的高层总结。

---

## 一、架构演进（关键变化）

| 维度 | 起点 | 现状 / 演进 |
|---|---|---|
| **语音架构** | 三段 **Pipeline**：STT→LLM→TTS | 加 `VOICE_MODE` 开关 → 可切 **speech-to-speech 实时（`gpt-realtime`）**，解决"卡一会"延迟；pipeline 作可回退默认。（分支 `feature/realtime-voice`） |
| **编排框架** | LiveKit Agents（调研后选定） | 不变——电话/打断/并发/转人工都靠它；换大脑不换框架 |
| **LLM 大脑** | 固定 Claude Haiku → 改默认 `gpt-4o-mini` | 加 `LLM_BASE_URL` → **任意 OpenAI 兼容模型**（GPT/Claude/Gemini/Qwen/DeepSeek/豆包/Kimi，含国内）。模型=配置项 |
| **STT / TTS** | OpenAI（zh） | env 可切：STT 加 Deepgram；TTS 加 Azure zh-CN；纯中文锁定 |
| **保安通知** | 一度想绑死企业微信 | 改为**可插拔多渠道**（`notify/dispatch.py`）→ **Telegram（主线，已合并）** + 企微/Discord，逗号分隔可同时推；企微/微信为国内生产最终落地 |
| **放行 / 转人工** | AI 全自动 | 加**两模式转人工**：管理员主动介入 + 客户要求；保安加入 AI 自动让位 |
| **数据存储** | SQLite 本地 | env 切换 → 生产 Neon Postgres（云、持久）；每次登记+开闸都留痕 |
| **回访识别** | 无 → 查一条 | 升级为**识别画像**（手机=人/车牌=车，match_type+次数+姓名+上次），按场景分级 |
| **访客接入** | 电话(Twilio SIP) | 扩为三形态：浏览器麦克风 `/voice`、扫码 `/qr`、电话；汇入同一 LiveKit room |
| **部署形态** | 本地 | 加**全云端**（Dockerfile/fly.toml + Railway/Fly + LiveKit Cloud + Neon），可彻底甩掉家用电脑 |
| **远程操作** | — | VS Code Tunnel 驱动本地 Claude Code + Tailscale 测语音 |
| **数据准确性** | 直接落库 | **AI 复述确认层**（车牌逐位/手机分组）+ **公司名单模糊匹配** + 车牌省份归一 |
| **门卫界面** | 实时对话流 + 表格 | 简化为**信息表格 + 放行按钮**（对话仍存库不显示） |

---

## 二、你提出的所有改进需求 / 方案变化（逐条 + 状态）

状态：✅已落地 · 🔀分支(待合) · 📝预备方案(文档) · ⏳待真机验证

| # | 你提出的需求 / 变化 | 决策 / 方案 | 状态 | 位置 |
|---|---|---|---|---|
| 1 | 调研要有证据、看推荐之外的框架 | 三路联网调研 + 决策矩阵 | ✅ | `FRAMEWORK_RESEARCH.md` |
| 2 | 先定计划再动手、开工不停、记录问题 | 计划获批后执行、PROGRESS/CHANGELOG 留痕 | ✅ | `PROGRESS.md` |
| 3 | 用单个 API key 把线路跑通（简单优先） | 默认全 OpenAI（`gpt-4o-mini`） | ✅ | `MODELS.md` |
| 4 | 除花钱/账号外全自动、用户只测 | `ACCEPTANCE_PROMPT.md` 全自动；本地 LiveKit、后台点放行 | ✅ | `ACCEPTANCE_PROMPT.md` `USER_TODO.md` |
| 5 | 给我要做的事配详细教程 | 图文教程（拿 key、LiveKit、扫码、远程） | ✅ | `USER_TODO.md` 等 |
| 6 | 扫码版要能测 | `/qr` + 隧道/Tailscale/Cloud 三路 | ✅ | `QR_DEMO.md` |
| 7 | 语音保持纯中文 | `STT_LANGUAGE=zh` 锁定、不开自动识别 | ✅ | 默认 |
| 8 | 数据要保存、存哪要想清楚、每次开闸留痕 | 本地 SQLite / 云 Neon；`call_events`+`confirmed_at` | ✅ | DESIGN §7.5 |
| 9 | 回访识别要全面、考虑使用场景 | `recognize()` 画像（车牌/手机/姓名/场景分级） | ✅ | DATA…/DESIGN |
| 10 | 常客名单 + 开闸时间列 | `/admin` 画像 + Dashboard 开闸时间 | ✅ | — |
| 11 | 记录版本迭代 + 计划变更 | `CHANGELOG.md` + 本文 | ✅ | 本文 |
| 12 | 转人工：管理员主动 + 客户要求，否则 AI | 两模式 + AI 让位 | ✅ | PRODUCT_FLOW §5.5 |
| 13 | 在外面用手机操作本地 Claude Code | VS Code Tunnel（主）+ Tailscale（测语音） | ✅(文档) | `REMOTE_ACCESS.md` |
| 14 | 彻底甩掉家用电脑（全云端） | Dockerfile + Railway/Fly + LiveKit Cloud + Neon | ✅(文档/产物) | `DEPLOY.md` |
| 15 | 微信发送（3 天内可落地，保安审核后放行） | 群机器人 webhook+链接放行（已具备）/ 自建应用按钮(后续) | 📝 | `WECHAT_PLAN.md` |
| 16 | AI 回复慢，要提速 | `preemptive_generation`+VAD 调优；**架构切 realtime** | ✅/🔀⏳ | `ARCHITECTURE_AB.md` |
| 17 | 语音识别错号码 → 加 AI 验证层 | 登记前复述车牌(逐位)+手机(分组)让访客确认 | ✅⏳ | `prompts.py` |
| 18 | UI 简陋难看；门卫界面太复杂 | 访客页美化；门卫页砍对话流→表格+按钮 | ✅⏳ | `web/server.py` |
| 19 | 车牌基础数据要准 + 输入公司名单自动匹配 | 公司名单模糊匹配 + 车牌省份归一（默认关） | 🔀 | `feature/data-matching` (PR #3) |
| 20 | 初步用 Telegram，企微备用/未来国内落地 | 多渠道（Telegram 主线已合并；企微预备） | ✅/📝 | `NOTIFY_SETUP.md` |
| 21 | 企微要不要公司/执照？ | 不需要，手机号即可建组织跑群机器人 | 📝 | `WECHAT_PLAN.md §零` |
| 22 | Telegram 与企微同步推进 | `NOTIFY_CHANNEL=telegram,wecom` 同时推 | ✅ | `dispatch.py` |
| 23 | **架构从三段换成 gpt-realtime** | `VOICE_MODE=realtime`（s2s），仍有转写+工具 | 🔀⏳ | `feature/realtime-voice` |
| 24 | 模型最终客户定，要能随时换任意模型 | `LLM_BASE_URL` 接任意 OpenAI 兼容端点 | ✅ | `MODELS.md` |
| 25 | Telegram 合进主分支、企微后续推进 | PR #2 已合并入 dev；企微代码在、默认关 | ✅ | dev |
| 26 | 记录好所有迭代/需求并总结成文档 | `CHANGELOG.md` 补全 + 本 `ITERATION_SUMMARY.md` | ✅ | 本文 |

---

## 三、版本时间线（详见 CHANGELOG.md）
v0.1 骨架 → v0.2 Dashboard → v0.3 浏览器/扫码/通知可插拔 → v0.4 最小化用户操作 → v0.5 单 key+扫码 →
v0.6 存储+回访画像 → v0.7 常客+开闸时间 → v0.8 审查/生产就绪 → v0.9 框架调研+一页README →
v0.10 文档归档 → v0.11 转人工 → v0.12 远程访问 → v0.13 跨平台(Win ARM64)修复 → v0.14 远程纠偏 →
v0.15 全云端部署 → v0.16 产品打磨(确认层/提速/简化/美化) → **v0.17 Telegram+企微多渠道(已合并)** →
**v0.18 公司名单匹配(分支)** → **v0.19 语音架构 A/B：pipeline→gpt-realtime(分支)** → **v0.20 模型可换**。

## 四、分支 / PR 状态
| 分支 | 状态 | 内容 |
|---|---|---|
| `claude/voice-agent-takehome-qzjbd2`(dev) | 主线 | 全部已合并能力 + Telegram + 模型可换 |
| `feature/wechat-push` (PR #2) | **已合并** | Telegram/企微多渠道 |
| `feature/data-matching` (PR #3) | 开着 | 公司名单匹配（默认关）——待你定是否合 |
| `feature/realtime-voice` | 开着(PR 待建) | `VOICE_MODE=realtime` 提速 A/B——待你真机验证 |

## 五、待办 / 计划池（详见 CHANGELOG 末尾）
真机电话+25秒计时 · 中文音色 A/B · TEN/Pipecat 架构对照 · 企微自建应用按钮回调 · Serverless 样例 · 海康真实抬杆 ·
realtime 真机验证后定是否设为默认。

## 六、需要你拍板/检查的
- 是否合并 `feature/data-matching`（公司名单匹配）与 `feature/realtime-voice`（提速）。
- realtime vs pipeline 真机 A/B 结果 → 定默认语音架构。
- 最终模型选型（客户）。
- 微信预备方案推进时机（方案 A 已具备/方案 B 按钮回调）。
- PRODUCT_FLOW 里仍待定的产品点（自动放行策略、回执、被访公司通知、黑白名单、隐私留存）。
