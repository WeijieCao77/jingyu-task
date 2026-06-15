# 🔄 Session 交接文档（新 Claude session 从这里开始）

> 给**新开的 Claude session**：读这一份就能接着干。本项目已迭代多轮，主分支可运行、测试全绿。
> 更细的：全局账本 `ITERATION_SUMMARY.md`、逐版本 `CHANGELOG.md`、逐轮决策 `PROGRESS.md`、文档索引 `DOCS.md`。

## 1. 这是什么
工业园区**语音访客登记**系统：未登记车辆（电话/扫码/浏览器）→ AI 门卫**中文对话**采集（车牌/单位/事由/手机/姓名）→ 推送保安（Telegram/企微/Discord/后台）→ 保安核对放行 → 抬杆。蓝色鲸鱼公司 take-home。

## 2. 架构（一句话）
**LiveKit Agents**（电话/打断/并发，不换）+ **realtime speech-to-speech**（默认提速，可 `VOICE_MODE=pipeline` 回退）。电话**拨号进来**=Twilio→LiveKit SIP→自动派发 agent（`TELEPHONY.md`），与扫码/浏览器汇入同一房间。**模型全 env 可换**（`LLM_BASE_URL`）。通知**可插拔多渠道**。黑白名单/公司名单/回访/转人工/FR-2 放行播报全在 `session_logic`，与接入形态无关。数据 SQLite/Neon。

## 3. 代码地图
```
src/visitor_agent/
  agent.py        LiveKit worker（电话/扫码/浏览器入口；VOICE_MODE 分支；主叫号预填手机；FR-2 放行播报；门卫来电→GuardQueryAgent 语音查数据 GUARD_PHONES）
  providers.py    STT/LLM/TTS/realtime 装配（唯一“换模型”点）
  prompts.py      中文门卫 prompt（含 AI 复述确认层 + 转人工 + 名单匹配确认）
  slots.py        槽位 + 车牌/手机规范化（含省份名→简称）
  session_logic.py 登记大脑 record/complete + 回访画像 + 名单匹配 + 黑白名单 + 放行播报payload（live & sim 共用）
  roster.py       公司名单模糊匹配（汉字+拼音；ROSTER_PATH 开启，默认关）
  access.py       黑白名单精确匹配（车牌/手机；ACCESS_LIST_PATH 开启，默认关）
  tenant.py       多租户：按被叫号码解析各租户配置（TENANTS_PATH 开启，默认关；产品化阶段1）
  guard_query.py  门卫数据助手（OpenAI/Claude 双驱动；多轮 history；count_visits 含放行status）
  notify/         dispatch(多渠道) + telegram(localhost兜底)/discord/wecom + gate(海康/stub) + common(老访客/名单高亮)
  db/             visits(+access_status/room) + call_events；_ensure_columns 增量迁移
  web/server.py   /voice /qr /dashboard(徽标·黑名单禁放行) /ask(数据中心:对话+筛选) /api/query(确定性) /admin /login(门卫口令 GUARD_ACCESS_KEY 中间件) /confirm(黑名单拒放行) /token；FR-2 approved 推送
  db/repo.py      SQLite 相对路径锚定项目根(持久化修复)；query_visits/count(status) 等只读查询
  sim/run_text.py 离线文本仿真（同一套逻辑，无需电话）
scripts/setup_sip.sh  电话接入：建 LiveKit 入站 trunk+dispatch（见 TELEPHONY.md）
tests/  94 个离线单测（沙箱缺 livekit 时 1 个 /token 用例跳过）   scenarios/ 仿真脚本
```

## 4. 今天已验证 / 状态（截至 v0.22）
- ✅ **真机已验证**（用户 Win11 ARM64 + livekit-server.exe）：Telegram 推送到手机、AI 复述确认、简化门卫界面、公司名单匹配（金鱼→鲸鱼）、真人语音端到端、**realtime 模式首句 ≈1.4s 明显更快**。
- ✅ **本轮已修/已加（v0.22，离线测试 49→74 全绿）**：realtime 合主线且与名单共存（FR-1）+ realtime 崩溃修复（P0-4）；**黑白名单**（NEW-2）；通知加**老访客/黑白名单**信息（NEW-1）；**放行后 AI 语音通知访客**（FR-2）；Telegram localhost 按钮兜底（①）；`/voice` 自动播放兜底（⑥）；测试隔离（②）。
- ⏳ **待用户真机验证（v0.22 新增项）**：realtime+名单同开、黑白名单命中卡片/徽标、FR-2 放行后访客是否听到 AI 播报、Telegram 兜底。**prompt 见 §9**。
- ⏳ **手机点放行链接**：用 Telegram 时 `PUBLIC_BASE_URL` 不能 localhost（已修+文档）；用户实测 Tailscale IP `http://100.67.103.51:8080` 可用。
- ✅ **v0.23 用户决策已落地**：默认 `VOICE_MODE=realtime`；**黑名单登记不放行**（系统拒绝放行）；白名单仍需保安确认（不自动放行）。
- ⏳ **v0.23 电话接入（任务第一必交项）**：`scripts/setup_sip.sh` + `TELEPHONY.md` 就绪（Twilio→LiveKit SIP→自动派发 agent；主叫号预填手机）。**待用户用 Twilio+LiveKit Cloud 真机拨打**（prompt 见 §9-E + `TELEPHONY.md` §六）。
- ✅ **v0.26 自主夜间**：真机电话反馈 FR-3~9（开场白/字母消歧/只复述被改项/手机校验/单位不在名单转人工/转人工推手机/不编造/自动挂断）+ 模型查询强制工具+分层 + **多租户 `tenant.py` 起步** + `UPGRADE_PLAN.md` 三层计划。离线 89 全绿（含真 .env）。FR-4 自动挂断、多租户 agent 接入 live-only 待真机验。
- 沙箱说明：这里 1 个 `/token` 用例失败只因未装 livekit 运行时包；装了即全绿。Notion/YouTube 受出网白名单限制读不到（任务全文已由用户粘贴据此研究）。

## 5. 分支 / PR
| 分支 | 状态 | 内容 |
|---|---|---|
| `main`（默认主线；原 dev 分支 `claude/voice-agent-takehome-qzjbd2`，PR #1） | **主线** | 全部 + **v0.22**：realtime 可选模式、黑白名单、通知增强(老访客/名单)、FR-2 放行播报、Telegram/`/voice`/测试 修复 |
| `feature/wechat-push` (PR #2) | 已合并 | — |
| `feature/data-matching` (PR #3) | 已合并 | — |
| `feature/realtime-voice` | **已并入 dev(v0.22)** | `VOICE_MODE` 增量手动并入主线（未回退 roster/base_url）；分支本身可弃 |

## 6. 协作节奏（重要）
- **本地 Claude Code**（用户 Windows 机器）跑真机测试（能连 OpenAI/LiveKit、有麦克风）；**这个远程 session** 改代码/文档、push。
- **凡是需要用户/本地 CC 做的事，都要给一段可复制的 prompt**（用户明确要求）。
- 用户提供密钥/账号；其余尽量自动化。改动记进 CHANGELOG/PROGRESS/ITERATION_SUMMARY。

## 7. 下一步候选（计划池）
- **真机验证 v0.22 新增项**（见 §9 prompt）：realtime+名单同开、黑白名单、FR-2 放行播报、Telegram 兜底。
- **客户拍板**：默认语音架构（pipeline/realtime）；白名单是否开 `AUTO_PASS_WHITELIST` 自动放行；黑名单命中处置强度。
- 公司名单 / 黑白名单：按用户真实数据调阈值/补条目。
- 企微推送预备方案推进（`WECHAT_PLAN.md`：群机器人已具备 / 自建应用按钮回调=方案 B 待做）。
- 真机电话(Twilio SIP)+25 秒计时、海康真实抬杆、Serverless 样例。

## 8. 新 session 怎么起步
1. 读本文 + `ITERATION_SUMMARY.md`（全局）+ `DOCS.md`（文档索引）。
2. 在 `main` 分支上工作；改完 push（Railway 自动部署源已是 main）。
3. 给用户的任何操作都配 prompt；改动同步进 CHANGELOG/PROGRESS。
4. 本地跑通参考 `ACCEPTANCE_PROMPT.md` / `SMOKE_CHECK.md`（Windows §C5）/ `NOTIFY_SETUP.md`。

## 9. 给用户的 v0.22 真机验证 prompt（复制给本地 Claude Code）
> 先 `git pull origin main` 同步到最新。x64 venv 跑：`pip install -r requirements.txt`。

**A. realtime + 公司名单 + 黑白名单 同时开（FR-1 + NEW-2）**
```
在我的 .env 里设：VOICE_MODE=realtime、ROSTER_PATH=roster.json、ACCESS_LIST_PATH=access.example.json
（access.example.json 仓库已带；roster.json 用我现有的）。起 livekit-server.exe --dev、agent worker、web。
打开 /voice 说话，验证三件事同时成立：① 首句快(≈1.4s 那种)②说错"蓝色金鱼"被纠成"蓝色鲸鱼"
③ 报 access.example.json 里的白名单车牌(沪A12345)→后台/Telegram 卡片显示 ✅白名单；
再报黑名单(沪A00000)→显示 ⛔黑名单、且不自动放行。把后台截图和卡片发我。
```

**B. 放行后 AI 语音通知访客（FR-2）**
```
保持 /voice 通话中，完成一次登记后在电脑 /dashboard 点"放行"（或点 Telegram 卡片的确认链接）。
验证：访客这端的 AI 是否开口说"已为您放行，请进，栏杆已抬起"。pipeline 和 realtime 各测一次。
若访客已挂断则应静默无报错。把 agent 日志里 data_received/approved 那几行发我。
```

**C. Telegram localhost 兜底（①）**
```
把 .env 的 PUBLIC_BASE_URL 故意设成 http://localhost:8080，NOTIFY_CHANNEL=telegram，
跑 sim --live。验证：手机仍收到卡片（这次没有按钮、但正文有"👉 确认放行：<链接>"），不再整条消息丢失。
```

**D. 黑名单"登记不放行"（NEW）**
```
.env 设 ACCESS_LIST_PATH=access.example.json，用黑名单车牌(沪A00000)走一遍登记。
验证：① 卡片/后台显示 ⛔黑名单 ② 后台该行是「⛔禁止放行」而非放行按钮 ③ 点确认链接显示"禁止放行"、
栏杆不抬。白名单(沪A12345)则正常显示 ✅、仍需保安点放行（不自动）。
```

**E. ☎️ 电话拨号进来（任务第一必交项，需 Twilio + LiveKit Cloud）**
> 完整步骤+排错见 `TELEPHONY.md`；给本地 CC 的 prompt 见 `TELEPHONY.md` §六。
```
我有 Twilio 号码和 LiveKit Cloud 项目。把 .env 的 LIVEKIT_URL 换成 Cloud（wss://<proj>.livekit.cloud）、
VOICE_MODE=realtime、NOTIFY_CHANNEL=telegram。在 Twilio 把号码 origination 指到我的 LiveKit SIP 主机，
跑 SIP_INBOUND_NUMBER=<号码> ./scripts/setup_sip.sh，起 agent worker(start)+web。
我用手机拨打那个号码：验证 AI 1~2s 开口、来电号码被预填为手机、25s 内手机收到卡片、放行后电话里听到"已放行"。
```
