# 🔄 Session 交接文档（新 Claude session 从这里开始）

> 给**新开的 Claude session**：读这一份就能接着干。本项目已迭代多轮，主分支可运行、测试全绿。
> 更细的：全局账本 `ITERATION_SUMMARY.md`、逐版本 `CHANGELOG.md`、逐轮决策 `PROGRESS.md`、文档索引 `DOCS.md`。

## 1. 这是什么
工业园区**语音访客登记**系统：未登记车辆（电话/扫码/浏览器）→ AI 门卫**中文对话**采集（车牌/单位/事由/手机/姓名）→ 推送保安（Telegram/企微/Discord/后台）→ 保安核对放行 → 抬杆。蓝色鲸鱼公司 take-home。

## 2. 架构（一句话）
**LiveKit Agents**（电话/打断/并发，不换）+ STT→LLM→TTS **pipeline**（默认，可切 `VOICE_MODE=realtime` speech-to-speech 提速）。**模型全 env 可换**（`LLM_BASE_URL` 可接任意 OpenAI 兼容端点，含国内）。通知**可插拔多渠道**。数据 SQLite/Neon。

## 3. 代码地图
```
src/visitor_agent/
  agent.py        LiveKit worker（电话入口；VOICE_MODE 分支 pipeline/realtime）
  providers.py    STT/LLM/TTS/realtime 装配（唯一“换模型”点）
  prompts.py      中文门卫 prompt（含 AI 复述确认层 + 转人工 + 名单匹配确认）
  slots.py        槽位 + 车牌/手机规范化（含省份名→简称）
  session_logic.py 登记大脑 record/complete + 回访画像 + 名单匹配（live & sim 共用）
  roster.py       公司名单模糊匹配（汉字+拼音；ROSTER_PATH 开启，默认关）
  guard_query.py  门卫查询 Agent（OpenAI/Claude 双驱动）
  notify/         dispatch(多渠道) + telegram/discord/wecom + gate(海康/stub) + common
  db/             visits + call_events（回访 recognize、常客 visitor_profiles）
  web/server.py   /voice /qr /dashboard(简化) /admin /guard_call /confirm /api/* /guard/query
  sim/run_text.py 离线文本仿真（同一套逻辑，无需电话）
tests/  51 个离线单测（全绿）   scenarios/ 仿真脚本
```

## 4. 今天已验证 / 状态
- ✅ **Telegram 推送已跑通**：用户真机收到访客卡片（`NOTIFY_CHANNEL=telegram` + token + chat_id）。
- ✅ **放行**：用户用**电脑后台 `/dashboard` 点放行**（方案 A）闭环成功。
- ⏳ **手机点放行链接**：localhost 手机打不开 → 需 cloudflared 隧道把 8080 暴露 + `PUBLIC_BASE_URL` 改公网（用户暂选 A，B 的 prompt 已给过）。
- ⏳ **真实语音 `/voice`、AI 复述确认、简化门卫界面、公司名单匹配、realtime 提速**：代码就绪+单测过，**待用户真机验证**（用户在 Windows 11 ARM64 本地用 livekit-server.exe + x64 venv 跑）。
- ✅ 主分支 51 测试全绿。

## 5. 分支 / PR
| 分支 | 状态 | 内容 |
|---|---|---|
| `claude/voice-agent-takehome-qzjbd2`(dev) | **主线** | 全部已合并：Telegram/多渠道、公司名单匹配、模型可换、AI 确认、提速参数、简化 UI、转人工、回访画像、云部署产物 |
| `feature/wechat-push` (PR #2) | 已合并 | — |
| `feature/data-matching` (PR #3) | 已合并 | — |
| `feature/realtime-voice` | **开着** | `VOICE_MODE=realtime` 提速 A/B，待真机对比后定是否合 |

## 6. 协作节奏（重要）
- **本地 Claude Code**（用户 Windows 机器）跑真机测试（能连 OpenAI/LiveKit、有麦克风）；**这个远程 session** 改代码/文档、push。
- **凡是需要用户/本地 CC 做的事，都要给一段可复制的 prompt**（用户明确要求）。
- 用户提供密钥/账号；其余尽量自动化。改动记进 CHANGELOG/PROGRESS/ITERATION_SUMMARY。

## 7. 下一步候选（计划池）
- 真机验证：`/voice` 语音 + AI 复述确认 + 25 秒计时 + 名单匹配 + 简化界面。
- realtime 提速 A/B（`feature/realtime-voice`）→ 定默认语音架构。
- 手机点放行：cloudflared 隧道 或 上云（`DEPLOY.md`，`PUBLIC_BASE_URL` 固定）。
- 企微推送预备方案推进（`WECHAT_PLAN.md`：群机器人已具备 / 自建应用按钮回调待做）。
- 公司名单：按用户真实名单调阈值/补别名。
- 产品决策点（`PRODUCT_FLOW.md §八`）：自动放行策略、回执、通知被访公司、黑白名单、隐私留存。
- 真机电话(Twilio SIP)、海康真实抬杆。

## 8. 新 session 怎么起步
1. 读本文 + `ITERATION_SUMMARY.md`（全局）+ `DOCS.md`（文档索引）。
2. 在 `claude/voice-agent-takehome-qzjbd2` 分支上工作；改完 push。
3. 给用户的任何操作都配 prompt；改动同步进 CHANGELOG/PROGRESS。
4. 本地跑通参考 `ACCEPTANCE_PROMPT.md` / `SMOKE_CHECK.md`（Windows §C5）/ `NOTIFY_SETUP.md`。
