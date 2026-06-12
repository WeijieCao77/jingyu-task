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

## 三、一步步搭（约 20 分钟，需 Twilio + LiveKit Cloud 账号）

1. **LiveKit Cloud**：建项目（免费）。`lk cloud auth` 登录 `lk` CLI（或把项目的 `LIVEKIT_URL/API_KEY/SECRET` 填进 `.env`）。拿到你的 **SIP 主机**（控制台 SIP 页，形如 `<proj>.sip.livekit.cloud`）。
2. **Twilio**：买一个带 Voice 的号码 → 建 **Elastic SIP Trunk** → Origination URI 填 `sip:<proj>.sip.livekit.cloud`（把该号码指向 LiveKit）。
   - 也可用更简的 **TwiML Bin**：`<Response><Dial><Sip>sip:<proj>.sip.livekit.cloud</Sip></Dial></Response>`，把号码的 Voice webhook 指向它。
3. **LiveKit 入站 trunk + 派发规则**（本仓库脚本一键）：
   ```bash
   SIP_INBOUND_NUMBER=+1XXXXXXXXXX ./scripts/setup_sip.sh
   ```
   它创建：inbound trunk（认你的号码）+ dispatch rule（每通来电进独立房间 `call-xxxx`，天然并发）。
4. **起 worker**（连 Cloud）：
   ```bash
   # .env: LIVEKIT_URL=wss://<proj>.livekit.cloud + API key/secret + OPENAI_API_KEY + VOICE_MODE=realtime
   python -m visitor_agent.agent start
   # 另开一个：python -m visitor_agent.web.server   （放行/Dashboard）
   ```
5. **拨打那个号码** → AI 门卫应在 1~2 秒内开口；走完对话 → 保安手机收到卡片 → 放行 → （FR-2）访客听到"已放行请进"。

> 25 秒计时 = Agent 开口到微信消息发出。realtime + caller-ID 预填手机，通常 1 轮（车牌+单位+事由）即可完成。

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

## 六、给本地 Claude Code 的 prompt（你来跑，需你的 Twilio/LiveKit Cloud 账号）

```
帮我把"打电话给 AI 门卫"这条链路在我本机跑通。我有 Twilio 账号和 LiveKit Cloud 项目。
1. 装 lk CLI 并 lk cloud auth；把我的 LiveKit Cloud 项目 LIVEKIT_URL/API_KEY/SECRET 写进 .env，
   VOICE_MODE=realtime、填 OPENAI_API_KEY、通知用 telegram（按 NOTIFY_SETUP.md）。
2. 指导我在 Twilio 建号码 + Elastic SIP Trunk，origination 指到我 LiveKit Cloud 的 SIP 主机
   （把主机名告诉我让我在控制台找/确认）。问我要这个号码。
3. 跑 SIP_INBOUND_NUMBER=<我的号码> ./scripts/setup_sip.sh 建 inbound trunk + dispatch rule；
   若我的 lk 版本 JSON 字段不一致，按 docs.livekit.io/sip 调整后重试，并把最终用的 JSON 给我。
4. 起 agent worker（start，连 Cloud）+ web server。让我用手机拨打那个号码实测：
   AI 是否 1~2s 开口、是否预填了我的来电号码为手机、25s 内我手机是否收到卡片、放行后我电话里是否听到"已放行"。
5. 把每步命令输出和我要点的地方写清楚；报错先自查再问我。
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
