# ☎️ 电话接入：访客拨打号码 → AI 门卫接听

> 任务的**第一必交项**：访客拨打入口张贴的号码 → Agent 接听 → 自然对话采集 → 推保安微信，**25 秒内**。
> 本文给出选型、架构、一步步搭建、国内 +86 替代方案，以及给本地 Claude Code 的 prompt。

---

## 一、链路（一句话）

```
访客手机拨号 → 运营商 → Twilio 号码(Elastic SIP Trunk)
   → SIP → LiveKit Cloud SIP 端点 → 匹配 inbound trunk + dispatch rule
   → 为本次来电建一个房间 call-xxxx → 运行中的 agent worker 被自动派发进房间
   → STT/realtime 对话采集 → 25s 内推保安(Telegram/企微) → 保安放行 → 抬杆
```

**不换框架**：电话只是又一种"接入形态"，和浏览器 `/voice`、扫码 `/qr` 一样最终汇入**同一个 LiveKit 房间 + 同一个 agent**。所以电话路打通后，复述确认、公司名单、黑白名单、回访识别、转人工、FR-2 放行播报**全部自动复用**，零改动。

> ⚠️ **必须用 LiveKit Cloud（免费版即可）跑电话**：你本地的 `livekit-server.exe --dev` 是回环地址，**公网打不进来**，Twilio 无法把电话送达。把 `.env` 的 `LIVEKIT_URL` 换成你的 Cloud 项目 `wss://<proj>.livekit.cloud`，agent worker 仍可在你本机跑（它是**外连** Cloud，不需要公网入站）。

---

## 二、为什么这么选（技术选型，答辩要点）

| 方案 | 取舍 | 结论 |
|---|---|---|
| **LiveKit Agents + LiveKit SIP**（选用） | 电话/打断/并发/转人工原生；SIP 把电话媒体桥进同一房间；和现有浏览器/扫码同栈 | ✅ 一套 agent 吃三种接入；被考察的"对话能力"留在自己手里 |
| Vapi / Retell（SaaS） | 起步快，但把"语音 agent"整体外包——**正是本题要考察的能力**被托管掉；锁定 + 难定制中文复述/名单 | ❌ 选型说明里作为对照：demo 快但不展示能力 |
| Twilio `<Gather>`/Studio 纯 IVR | 机械一问一答，不是 LLM 自然对话 | ❌ 违反"Human Friendly" |
| Pipecat + 自接 SIP | 也可，但 SIP/并发要自己拼；LiveKit SIP 现成 | 备选 |

- **号码来源 = Twilio**（demo 最可复现，国际号即可；任务允许"用你自己的电话作为 Demo"）。
- **realtime（默认）**：speech-to-speech 把首句压到 ≈1.4s，是稳过 25s 的关键（pipeline 三段串联冷启动更慢）。
- **主叫号即手机号**：SIP 来电带 caller-ID（`sip.phoneNumber`），代码已**自动预填手机槽**——电话场景下访客的来电号码就是要采集的手机号，省一问、还免去听错号码，并立刻触发回访/黑白名单匹配。

---

## 三、手把手：从注册到打通（约 30–40 分钟）

> **你（人）只做网页上的注册/购买/复制粘贴**；命令行/配置/起服务全部交给本地 Claude Code（prompt 在 §六）。

### 第 1 步：注册 LiveKit Cloud（免费，≈5 分钟）
1. 打开 **https://cloud.livekit.io** → 右上 **Sign Up**（用 Google/GitHub 邮箱皆可）。
2. 登录后 **Create Project**，名字随意（如 `visitor-agent`）。
3. 左侧 **Settings → Keys** → **Create Key** → 记下三样（一次性显示，存好）：
   - `LIVEKIT_URL`：形如 `wss://visitor-agent-xxxx.livekit.cloud`
   - `API Key`（`API...` 开头）、`API Secret`
4. 左侧找 **SIP**（或 Settings → Project 里的 SIP URI）→ 记下 **SIP 主机**：形如
   `visitor-agent-xxxx.sip.livekit.cloud`。第 3 步 Twilio 要把电话指到它。
> 免费额度对 demo 足够；不需要绑卡。

### 第 2 步：注册 Twilio + 买号码（≈10–15 分钟）
1. 打开 **https://www.twilio.com/try-twilio** → 注册（邮箱 + 手机验证；你的中国手机号可以收验证码）。
   注册完是**试用账户**，送 ~$15 额度，够买号码 + 测试很多通。
2. **试用账户两个限制（重要）**：
   - 只能和**已验证的号码**通话：Console → **Phone Numbers → Verified Caller IDs → Add**，把**你自己的手机号**（+86...）加进去并接验证码——这样你就能用自己手机拨测试。想让亲朋好友测，要么把他们号码也验证，要么升级账户（充 $20 即去除限制）。
   - 接通后会先播一句"试用账户"提示音，正式演示前建议升级去掉。
3. **开通国际语音地理权限**（让 +86 能打进来）：Console 搜 **Geo Permissions**（Voice Geographic Permissions）→ 把 **China** 勾上。
4. **买号码**：Console → **Phone Numbers → Buy a Number** → 国家选 **United States**（最便宜稳妥，≈$1.15/月）→ 勾 **Voice** 能力 → Search → 任选一个 → **Buy**。
   - 这个 +1 号码就是"入园电话"。（+86 号码 Twilio 基本拿不到——国内落地见 §四。）
5. **把号码指到 LiveKit（TwiML Bin 法，最简单）**：
   1) Console 搜 **TwiML Bins** → **Create new TwiML Bin** → 名字 `to-livekit`，内容（把主机换成你第 1 步记下的）：
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <Response><Dial><Sip>sip:visitor-agent-xxxx.sip.livekit.cloud</Sip></Dial></Response>
   ```
   2) **Phone Numbers → Manage → Active numbers** → 点你的号码 → **Voice Configuration**：
      "A call comes in" 选 **TwiML Bin** → 选 `to-livekit` → **Save**。

### 第 3 步：LiveKit 侧入站规则 + 起服务（全部交给本地 CC）
把 §六 的 prompt 丢给本地 Claude Code。它会：装 `lk` CLI → 把 Cloud 三件套写进 `.env` → 跑
`SIP_INBOUND_NUMBER=+1你的号码 ./scripts/setup_sip.sh`（建 inbound trunk + dispatch rule，每通来电独立房间）
→ 起 `python -m visitor_agent.agent start` + web server。

### 第 4 步：拨打实测
用你**已验证**的手机拨那个 +1 号码 →（试用提示音后）AI 门卫 1~2 秒开口 → 对话登记 →
25 秒内 Telegram 收到卡片 → 点放行 → 电话里听到"已放行请进"（FR-2）。
若 `.env` 配了 `GUARD_PHONES=+86你的号`，**用这个号拨入会变成"语音数据助手"**——想测访客流程就换一个号码或临时清空该项。

> 25 秒计时 = Agent 开口到推送发出。realtime + caller-ID 预填手机，通常 1 轮（车牌+单位+事由）即可完成。

### 费用小账
号码 $1.15/月 + 接听 ≈$0.0085/分 + LiveKit 免费额度 + OpenAI realtime ≈$0.2-0.5/分 → **一次完整 demo 通话 < ¥5**；试用送的 $15 够全部测试。

---

## 四、国内 +86 落地（生产）

- Twilio 不易发 +86 号、且国内主被叫合规受限。**生产换国内 SIP 中继**：阿里云语音服务 / 容联七陌 / 声网 等提供 SIP trunk 的服务商，把 origination 指到 LiveKit SIP——**LiveKit SIP 这层不变**，只换号码/中继来源。
- 备案、号码资质按服务商要求办；demo 阶段用 Twilio 国际号验证全链路即可，答辩说明国内替换路径。

---

## 五、保安微信（与电话同等"接入/触达"选型）

- **现状（已实现）**：Telegram（demo 最快到手机）/ 企业微信群机器人（生产，`notify/wecom.py`）/ Discord，逗号可多推；卡片带放行链接 + 老访客/黑白名单高亮。
- **个人微信（任务允许"个人微信亦可 Demo"）**：可评估 **QClaw / OpenClaw**（腾讯基于 OpenClaw 的产品，扫码绑定个人微信、可收发消息/语音）——把放行卡片推到个人微信。优点是真·微信触达；**风险**：个人微信自动化历来有 ToS/封号风险，QClaw 是腾讯官方产品相对可控，但仍建议生产用**企业微信**（合规、原生按钮回调见 `WECHAT_PLAN.md` 方案 B）。
- 结论：demo = Telegram（秒到）；生产国内 = 企业微信；个人微信(QClaw) 作为"真微信触达"的可选项，答辩讲清取舍。

---

## 五·五、门卫打电话查数据（同号码，按来电号码区分角色）

同一个入园号码：**访客**打进来=登记；**门卫**打进来=语音问数据（"今天放行了多少辆""高峰时段"）。靠 caller-ID 区分：
- `.env` 设 `GUARD_PHONES=+8613xxxxxxxx`（逗号分隔 1~2 个门卫手机号）。
- 来电号码在名单 → 路由到 **语音数据助手 `GuardQueryAgent`**（复用 `/ask` 同一套安全只读查询工具，纯语音问答，不登记）；否则按访客登记。留空=所有来电都按访客。
- 网页端同理用 `GUARD_ACCESS_KEY` 口令守 `/dashboard /ask /admin`（访客的 `/voice` `/qr` 不受影响）。详见 `SETUP_GUIDE.md`。

## 六、给本地 Claude Code 的 prompt（你照 §三 注册好账号后用；配置沿用 .env 不再重复问）

```
帮我把"打电话给 AI 门卫"在我本机跑通（参考仓库 TELEPHONY.md §三）。配置一律沿用现有 .env，
缺的才问我。我已注册 LiveKit Cloud（有 URL/KEY/SECRET 和 SIP 主机名）和 Twilio
（已买 +1 号码、已加 Verified Caller ID、已开 China geo 权限、号码已用 TwiML Bin 指到我的 SIP 主机）。
1. 切换电话模式：把 .env 的 LIVEKIT_URL/API_KEY/SECRET 换成我的 Cloud 三件套
   （本地 dev 那组留作注释，方便切回）。OPENAI/TELEGRAM/名单/口令等沿用 .env，不要再问。
2. 装 lk CLI 并认证（lk cloud auth，或直接用 .env 三件套作环境变量）。
3. 问我要 Twilio 号码，跑 SIP_INBOUND_NUMBER=<号码> ./scripts/setup_sip.sh 建 inbound trunk
   + dispatch rule；若我的 lk 版本 JSON 字段不一致，按 docs.livekit.io/sip 调整后重试，最终 JSON 给我。
   用 lk sip inbound list / lk sip dispatch list 验证。
4. 起 agent worker（python -m visitor_agent.agent start）+ web server。
5. 让我用已验证的手机拨打那个号码，帮我确认并计时：AI 几秒开口、来电号码是否自动成为手机号、
   25 秒内 Telegram 是否收到卡片、点放行后电话里是否听到"已放行请进"。
   注意：若 .env 配了 GUARD_PHONES 且我用的正是那个号，会进"语音数据助手"而非登记——提醒我换号或临时清空再测访客流。
6. 每步输出和我要点的地方写清楚；报错按 TELEPHONY.md §七排查；最后报"接通→卡片发出"的总秒数。
```

---

## 七、排错速查

| 症状 | 可能原因 / 处置 |
|---|---|
| 拨过去忙音/挂断 | Twilio Trunk origination 没指对 LiveKit SIP 主机；或号码没绑到 Trunk/TwiML |
| 接通但没人说话 | agent worker 没在跑、或连的是本地 dev server 而非 Cloud；`LIVEKIT_URL` 要是 Cloud |
| 进来但没进房间 | dispatch rule 没建或号码没匹配上 inbound trunk（`lk sip inbound/dispatch list` 查） |
| `lk sip ... create` 报错 | CLI 版本字段差异，按 docs.livekit.io/sip 的当前 JSON 调整（脚本里是常见格式） |
| 手机号没自动预填 | 该 trunk/provider 未透传 caller-ID；属增强项，不影响对话照常问手机 |
| 首句慢、超 25s | 确认 `VOICE_MODE=realtime`、key 有 gpt-realtime 权限；pipeline 冷启动更慢 |
