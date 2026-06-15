# 📚 文档汇总（索引）

本仓库全部文档的分类索引——按"产品 / 选型 / 部署验收 / 开发记录"四类归好，每篇标注**用途**、**读者**、**一句话总结**。建议从这里进。

---

## 🔄 新开 Claude session？先读这一篇
> **[SESSION_HANDOFF.md](SESSION_HANDOFF.md)** —— 交接文档：项目是什么、架构、代码地图、今天已验证状态、分支/PR、协作节奏、下一步候选。**新 session 读它就能接着干。**

---

## 🧭 想快速了解，从这几篇开始
1. **[README.md](README.md)** —— 一页速览：架构图 + 部署 + 环境变量。
2. **[GUIDE.md](GUIDE.md)** ⭐ —— **详细操作指南**：跑通 / 部署（本地 + Windows + 云端）/ 环境变量全表 / 演示 / 排错，自包含一站式。
3. **[PRODUCT_FLOW.md](PRODUCT_FLOW.md)** —— 全流程 + 访客/管理者双视角 + 产品决策点（**产品评审看这篇**）。
4. **[FRAMEWORK_RESEARCH.md](FRAMEWORK_RESEARCH.md)** —— 框架市场调研：为什么选 LiveKit、竞品优势、为什么不用（**答辩选型看这篇**）。

> 👉 **你（人）要做账号/操作 + 给本地 CC 的 prompt，看这一篇：[SETUP_GUIDE.md](SETUP_GUIDE.md)**（v0.23 总指南，含电话/Telegram/黑白名单/FR-2 验证 prompt）。

---

## 一、产品与流程

| 文档 | 用途 | 读者 | 一句话 |
|---|---|---|---|
| **[PRODUCT_FLOW.md](PRODUCT_FLOW.md)** | 产品全流程 + 双视角 + 决策点 | 产品/评审/你 | 跑起来什么样、访客看到什么、管理者得到什么、PM 待拍板 8 点 |
| **[DEMO_SCRIPT.md](DEMO_SCRIPT.md)** | 1–2 分钟演示脚本 | 录 demo 的人 | 分镜 + 旁白 + 计时口径 |
| **[WECHAT_PLAN.md](WECHAT_PLAN.md)** | 微信推送预备方案 | 产品/你 | 3 天内落地：群机器人+链接放行（已具备）/ 自建应用按钮回调 |

## 二、技术选型与设计（答辩核心）

| 文档 | 用途 | 读者 | 一句话 |
|---|---|---|---|
| **[ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md)** ⭐ | **每个决策：为什么+优势+根因+是否跟模型相关** | 答辩 | 全迭代架构决策记录，附"优势×模型相关性"汇总表 |
| **[DESIGN.md](DESIGN.md)** | 选型理由 + 证据 + 延迟预算 + 中国落地 + 存储 + 回访 + Serverless | 答辩/工程 | 为什么 Pipeline 不用 s2s、各环节选型、25 秒预算、数据存哪、回访画像 |
| **[FRAMEWORK_RESEARCH.md](FRAMEWORK_RESEARCH.md)** | 框架市场调研报告 | 答辩/选型 | LiveKit vs Pipecat/TEN/Vapi/Retell/云直连，决策矩阵 + 为什么不用它们 |
| **[MODELS.md](MODELS.md)** | 模型可换架构 | 你/客户/答辩 | 现在用哪个模型、怎么换、客户可选任意模型（含国内）、加新 provider |

## 三、部署与验收（你和本地 Claude Code 用）

| 文档 | 用途 | 读者 | 一句话 |
|---|---|---|---|
| **[SETUP_GUIDE.md](SETUP_GUIDE.md)** ⭐ | **总指南：账号+操作+逐项 prompt** | 你 | v0.23 一站式：要哪些账号、手把手、给本地 CC 的 prompt（含电话） |
| **[TELEPHONY.md](TELEPHONY.md)** ☎️ | 电话接入（拨号进来） | 你/本地 CC | Twilio→LiveKit SIP→agent；选型/国内替代/排错/prompt |
| **[ACCEPTANCE_PROMPT.md](ACCEPTANCE_PROMPT.md)** | 一键验收 prompt | 喂给本地 Claude Code | 全自动起服务，只需 1 个 OpenAI key |
| **[USER_TODO.md](USER_TODO.md)** | 你要做的事 + 图文教程 | 你 | 怎么拿 API key / LiveKit 免费号、花费预期、安全 |
| **[QR_DEMO.md](QR_DEMO.md)** | 手机扫码版 | 你/本地 CC | 路 A(LiveKit Cloud) / 路 B(同 WiFi 零账号) |
| **[SETUP_CHECKLIST.md](SETUP_CHECKLIST.md)** | 逐步部署清单 | 你/本地 CC | 从密钥到真实电话(Twilio→LiveKit SIP)的每一步 |
| **[SMOKE_CHECK.md](SMOKE_CHECK.md)** | 首次真跑排查 | 本地 CC/你 | 症状→原因→处置 + 验收断言 + 未验证项 |
| **[DEPLOY.md](DEPLOY.md)** | 全云端部署（甩掉家里电脑） | 你/cowork | Railway/Fly + LiveKit Cloud + Neon，手机随处测；含部署 prompt |
| **[REMOTE_ACCESS.md](REMOTE_ACCESS.md)** | 在外用手机操作家里电脑 | 你/本地 CC | VS Code Tunnel 驱动本地 Claude Code + Tailscale 测语音 |
| **[TEST_TASKS.md](TEST_TASKS.md)** | 本地真实联调任务 | 喂给本地 Claude Code | 5 条测试 prompt，跑完回报 |

## 四、开发记录（过程留痕）

| 文档 | 用途 | 读者 | 一句话 |
|---|---|---|---|
| **[ITERATION_SUMMARY.md](ITERATION_SUMMARY.md)** | 需求与迭代总结（高层账本） | 你/检查 | 架构演进 + 你提的每条需求/变化+状态 + 时间线 + 分支/PR + 待拍板 |
| **[CHANGELOG.md](CHANGELOG.md)** | 版本 + 计划变更时间线 | 你/审查 | v0.1→最新每轮改了什么、计划怎么变、计划池 |
| **[PROGRESS.md](PROGRESS.md)** | 每轮决策 + 卡点 | 你/审查 | 决策理由、卡点处理、快速验收顺序 |

---

## 五、代码导航（配合文档看）

```
src/visitor_agent/
  agent.py          LiveKit 电话 worker（入口）      providers.py   STT/LLM/TTS 装配（env 切换）
  prompts.py        中文门卫 system prompt           slots.py       槽位模型 + 规范化
  session_logic.py  登记大脑（record/complete + 回访识别画像，live & sim 共用）
  guard_query.py    门卫查询 Agent（OpenAI/Claude 双驱动）
  notify/           dispatch + discord/telegram/wecom + gate(海康 ISAPI/stub) + common
  db/               visits + call_events 模型/仓储（回访 recognize、常客 visitor_profiles）
  web/server.py     /voice /qr /dashboard /admin /confirm /api/* /guard/query
  sim/run_text.py   离线文本仿真（同一套对话逻辑，无需电话）
tests/              94 个离线单测           scenarios/   仿真脚本
```

---

## 阅读建议（按角色）

- **你（产品 + 验收）**：`PRODUCT_FLOW.md` → `USER_TODO.md` → `ACCEPTANCE_PROMPT.md`。
- **答辩准备**：`DESIGN.md` → `FRAMEWORK_RESEARCH.md` → `CHANGELOG.md`。
- **本地 Claude Code 跑通**：`ACCEPTANCE_PROMPT.md` + `SMOKE_CHECK.md`（+ `QR_DEMO.md` 测扫码）。
