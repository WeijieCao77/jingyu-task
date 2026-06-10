# 技术选型与设计说明（DESIGN）

> 本文回答答辩的核心问题：**为什么选这个、不选那个**。每个决策都附了取舍与证据。

## 0. 一句话架构

> LiveKit Agents（编排）+ Twilio（电话/SIP）+ **STT→LLM→TTS pipeline**（OpenAI STT · Claude Haiku 4.5 · OpenAI TTS）+ 企业微信群机器人 Webhook（推送）+ SQLite/Neon（数据）。抬杆为 stub。

---

## 1. 题眼：Pipeline vs Speech-to-Speech —— 选 Pipeline

这是整道题最关键的判断。我们对比了两条路线：

| 维度 | **Pipeline (STT+LLM+TTS)** ✅ | Speech-to-Speech (OpenAI Realtime / Gemini Live) |
|---|---|---|
| 结构化提取 | STT 出**文本**→直接解析车牌/公司/手机/事由→可靠触发微信 | 返回音频，要**额外转写**才能拿字段（多一跳延迟与成本） |
| 中文音色 | 可上中文原生 TTS（Qwen3-TTS≈97ms、CosyVoice2≈150ms、MiniMax<250ms） | OpenAI/Gemini 以英文为主，中文韵律/多音字偏弱 |
| 成本/分钟 | ~$0.02–0.06（自建）| Realtime ~$0.18–0.46 |
| 单轮延迟 | 优化后 ~400–600ms | ~300–800ms（差距 200–400ms，听感无感知） |
| 可换 LLM | 任意（这里用 Claude）| 锁定厂商音频模型 |

**结论**：本业务**必须拿到文本**做下游自动化（填槽、发微信、写库、查询），这点直接淘汰 s2s；中文音色与成本进一步加分。延迟差距已小到不构成理由。

> 证据：Realtime 首音 300–600ms、pipeline 600ms–1.5s，差距"在多数会话场景下无法感知"；中文 TTS 盲测中 Qwen3-TTS/CosyVoice/MiniMax 显著优于英文为主模型。
> 来源：[OpenAI gpt-realtime](https://openai.com/index/introducing-gpt-realtime/) · [Real-time vs Cascading (Softcery)](https://softcery.com/lab/ai-voice-agents-real-time-vs-turn-based-tts-stt-architecture) · [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) · [CosyVoice](https://github.com/FunAudioLLM/CosyVoice)

---

## 2. 编排框架：LiveKit Agents

候选：LiveKit / Pipecat / TEN Framework（声网）/ Vapi·Retell（SaaS）/ 纯自建。

**选 LiveKit**，因为它把"像真人"和"能上生产"最难的部分开箱抽象掉了：
- **原生 SIP 电话**（Twilio 官方接入文档），不用自己搭媒体栈；
- **生产级自适应打断 / turn-taking**（v1.5），中文用 multilingual 语义 turn detector；
- **天然并发**：每通电话 = 一个独立 job/room、独立会话，无共享可变状态（→ 加分项"多路并发"自动满足）；
- **STT/LLM/TTS 可插拔**：换中文 TTS 只是改 `providers.py` 一个分支 + env；
- 文档最好、7 天可交付，答辩能完整讲清 pipeline 架构。

**没选**：Pipecat（同样优秀，但 SIP 不如 LiveKit 一等公民、有过 `aggregation_timeout` 延迟坑）；TEN（中英双语 turn detection 很适合中文，但英文文档少、7 天有风险——列为**下一版 A/B 候选**）；Vapi/Retell（3 分钟出 demo，但"自建工程能力"故事弱、有锁定，列为"≤2 天极速兜底"）。

> 来源：[LiveKit Telephony](https://docs.livekit.io/telephony/accepting-calls/inbound-twilio/) · [LiveKit Turn Detection](https://livekit.com/blog/turn-detection-voice-agents-vad-endpointing-model-based-detection) · [TEN VAD/Turn (Agora)](https://www.agora.io/en/blog/making-voice-ai-agents-more-human-with-ten-vad-and-turn-detection/)

---

## 3. 电话方案：Twilio 美国号（demo）

候选：Twilio / Telnyx / Plivo / SignalWire / 阿里云·SIP Trunk。

- **demo 选 Twilio**：号 $1/月、接听 $0.0085/分钟、和 LiveKit 一等公民 SIP 集成、**中国手机可拨打美国号**、5 分钟拿号。开发者在美国，这是出 demo 最快且最稳的路径。
- **Telnyx** 私有骨干网延迟略低、单价更便宜，列为备选。

**中国生产路径（trade-off 故事）**：MIIT 规定境外 VoIP 不能直连中国 PSTN；要拿 +86 号需**中国实体 + ICP + 号码实名**。生产架构应为 **阿里云/腾讯云 SIP Trunk → 部署在中国区的 LiveKit/Pipecat**。美国个人绕不过实体这一步，过渡可用香港/新加坡可拨号码。**demo 证明 AI 栈可用，生产换号码层即可。**

> 来源：[Twilio×LiveKit](https://docs.livekit.io/telephony/accepting-calls/inbound-twilio/) · [Twilio China 限制](https://support.twilio.com/hc/en-us/articles/360016488474-Calling-Limitations-to-China) · [阿里云 SIP Trunk](https://www.alibabacloud.com/blog/introduction-to-sip-trunking_600630) · [ICP 指南](https://msadvisory.com/icp-license-china/)

---

## 4. STT / LLM / TTS 具体模型

v1 在"你当前拥有 OpenAI + Anthropic 两个账号"的约束下落地，全部 env 可切：

| 环节 | v1 选型 | 理由 / 升级路径 |
|---|---|---|
| **STT** | OpenAI `gpt-4o-transcribe`（zh）| 易开通、中文可用、流式低延迟。升级：阿里 Paraformer-v2（中文 WER 最低、数据在中国区）或 Deepgram Flux |
| **LLM** | **Claude Haiku 4.5**（`claude-haiku-4-5`）| 快/便宜（$1/$5 每 MTok）、中文强、工具调用稳、**无 thinking → 最低单轮延迟**；负责"自然对话 + 填槽 + 完成判定" |
| **TTS** | OpenAI `gpt-4o-mini-tts` | 同账号可用。中文音色想更自然 → 一行 env 切 MiniMax(海螺)/Azure zh-CN/Qwen3-TTS |

> LLM 大脑选 Claude Haiku：voice 场景关掉 thinking 是最低延迟，Haiku 4.5 在中文口语与工具调用上完全够用且最省。来源：claude-api 参考（model id `claude-haiku-4-5`，$1/$5 per MTok）。

---

## 5. 微信推送：企业微信群机器人 Webhook

候选：企微群机器人 / 企微自建应用 API / 个人微信(itchat·wechaty) / Server酱·WxPusher。

- **选企微群机器人 Webhook**：秒级建群拿 URL、个人手机号即可注册免费版、无需营业执照、20 条/分钟够用、国际可用。
- **"保安确认放行"**：群机器人是单向推送，所以用**消息内带 token 的确认链接**——保安在企微内置浏览器点 `/confirm?token=…`，后端校验后触发抬杆。生产可升级为**企微自建应用模板卡片**（带按钮回调）。
- **个人微信一律不用**：itchat/wechaty 违反 ToS、封号风险高——主动选合规路径本身就是答辩加分。WxPusher 作为兜底。

> 来源：[企微群机器人](https://bika.ai/help/reference/integration/we-com) · [WxPusher](https://wxpusher.zjiecode.com/docs/) · [wechaty 封号 issue](https://github.com/wechaty/wechaty/issues/2221)

---

## 6. 抬杆：海康 ISAPI（demo stub）

抬杆控制器在**园区内网**、非公网，开发者笔记本无法直连，故 demo 打日志 stub。真实形态（已写进 `notify/gate.py` 作为活文档）：
```
PUT http://<controller-ip>/ISAPI/ITC/Entrance/barrierGateCtrl/channels/1
<BarrierGate><cmd>open</cmd></BarrierGate>      # digest auth
```
答辩口径："离 demo 只差一个内网 HTTP 调用。"

---

## 7. 数据与加分项

- **数据**：SQLite（本地）/ Neon Postgres（云）—— 换 `DATABASE_URL` 即可，零代码改动。`visits` 表 + plate/phone 索引。
- **回访识别 ✅**：plate 一进来就查历史，命中则预填单位/事由并提示 LLM"直接确认、别重问"（见 `session_logic.RegistrationSession.record`）。
- **门卫查询 Agent ✅**：保安自然语言查数据（"本周多少车""高峰时段""张师傅来几次"）。用**安全的参数化工具**（count_visits / list_visits / busiest_hours）而非裸 text-to-SQL（防注入），Claude 选工具+措辞。CLI 与 `/guard/query` 两种入口。
- **多路并发 ✅**：LiveKit 每通电话独立 job，`RegistrationSession` 每会话独立，无全局可变状态。
- **Serverless ⚠️ 诚实边界**：LiveKit/Pipecat 的**音频层无法真 Serverless**（Cloudflare Workers 50ms CPU 上限、无长连接），必须常驻进程（VPS/Fly/Railway/容器）。可 Serverless 的是：**`/confirm` 与 `/guard/query` 端点 + Neon DB + CI/CD**。这点讲清=加分，讲不清=被问倒。

---

## 8. 25 秒延迟预算（怎么守住）

```
接通 → Agent 开口（greeting，立即）
理想 3 轮：每轮 ≈ 用户说话 2s + (STT 0.1–0.3 + LLM 首token 0.3–0.6 + TTS 首音 0.1–0.2)s ≈ 0.6–1.1s
3 轮 agent 延迟 ≈ 2–3s，对话总时长 ≈ 12–18s
complete → 企微 webhook POST ≈ 0.2–0.5s
→ 从开口到微信发出 ≈ 15–20s，留有余量 < 25s
```
设计上压低延迟：Haiku 关 thinking、流式 STT/TTS、批量提问减少轮次、tool 调用与语音并行。

---

## 9. AI 辅助编码（Vibe Coding）说明

本项目大量使用 Coding Agent 协作：先做**市场调研**（并行子代理搜证据、带 source）再定架构；用 claude-api 官方参考确认 Claude 模型与接法；核心对话逻辑与 LiveKit/Anthropic API 用安装后**introspect 真实签名**而非凭记忆；离线**单测 + 文本仿真**在无电话/密钥环境下验证逻辑。决策与卡点记录在 `PROGRESS.md`，便于审查 AI 产出。
