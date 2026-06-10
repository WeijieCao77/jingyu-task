# 语音 Agent 框架选型调研报告（2026-06）

> 回答三个问题：**在有其他框架可用的情况下，我们为什么用 LiveKit Agents？其他框架各自的优势是什么？为什么不用它们？**
> 数据来源：三路并行联网调研（2026 年 6 月时点），所有结论附 Sources。本报告同时作为答辩的选型依据。

---

## 0. 结论先行（TL;DR）

市场上能做"电话呼入的中文语音 Agent"的方案分三类：**开源编排框架**（LiveKit / Pipecat / TEN / Dograh / Bolna / Vocode）、**托管 SaaS**（Vapi / Retell / Bland / Inworld 等）、**电话原生/云直连**（Twilio ConversationRelay / OpenAI Realtime+SIP / Gemini Live / Amazon Nova Sonic / 阿里云·火山引擎）。

**我们选 LiveKit Agents**，核心理由四条：
1. **原生 SIP 电话是第一方能力**（甚至可以不要 Twilio），7 天内能跑通呼入电话的最短路径；
2. **打断/turn-taking 是生产级**（语义化转向检测 86% precision / 100% recall），"像真人"这条硬指标不用自己造轮子；
3. **STT/LLM/TTS 全可插拔**——中文音色升级（CosyVoice2/MiniMax/Azure zh-CN）只换插件不动架构，这是对"中文质量"风险的对冲；
4. **无锁定 + 可答辩**：Apache-2.0、可自托管、社区最大（379 contributors），逻辑是纯 Python 可测试可迁移；规模化后成本比 SaaS 低 60–80%。

每个竞品都有真实优势（见下），但在"中文 + 电话 + 7 天 + 答辩考工程品味"这四个约束同时成立时，没有一个综合分超过 LiveKit。

---

## 1. 开源编排框架对比

| 维度 | **LiveKit Agents**（我们用的） | Pipecat | TEN Framework（声网） | Dograh / Bolna / Vocode |
|---|---|---|---|---|
| GitHub（2026-06） | 10.9k★, 379 贡献者, v1.5.17 | 12.8k★, v1.3.0 | 10.7k★, 多语言代码库 | 4.3k★ / 665★ / 649★ |
| 原生 SIP 电话 | **第一方**（可不经 Twilio） | 间接（Daily/Twilio 适配器） | 有（extension） | 间接/有限 |
| 打断/转向检测 | 语义化（86% prec / 100% rec） | VAD + Cartesia turns | **中英双语 98.9%（中文最强）** | 基础 |
| 并发模型 | 单进程多 agent + job 分发 | **GIL 限制：1 容器/通话** | Agora RTC 承载 | 容器/不明 |
| 中文适配 | 好（靠可插拔 provider） | 好（同左） | **最佳（原生双语）** | Dograh 仅英文 |
| 7 天可交付 | **高** | 中 | 中低（文档碎、多语言栈） | 低/低/低 |
| 答辩可辩护性 | **很高** | 高 | 中高（需解释声网背景） | 低 |

### 各框架的真实优势 与 我们不用的原因

**Pipecat**（最强对手）
- ✅ 优势：星数最高（12.8k）、40+ provider、v1.3 多 agent 总线、Pipecat Cloud GA、管线完全自组装（掌控力最强）。
- ❌ 不用：**没有原生 SIP**（电话要绕 Daily/Twilio 适配器多一跳）；**Python GIL 导致一容器一通话**，并发要自己上容器编排——7 天预算吃不下这个 DevOps 量；2026 年有从业者称其为"最难部署上生产的语音框架"。
- 📌 定位：MVP 后做自托管/掌控力 A/B 的首选候补。

**TEN Framework**（中文场景理论最优）
- ✅ 优势：**TEN VAD + 双语转向检测是为中文而生**（中文完句判断 98.9%）；STT/LLM/TTS 并行而非串行（自称省 60–70% 延迟）；原生 SIP；声网十年 RTC 底座。
- ❌ 不用：文档碎片化（theten.ai/Agora/GitHub 三处）、C/C++/Rust/Python/TS 混合栈调试成本高、英文教程生态薄、延迟数据均为自报——**7 天交付风险过高**。若有 30 天，值得认真评估。
- 📌 定位：中文 turn-detection 若成为瓶颈，第一个借鉴/对照对象。

**Dograh / Bolna / Vocode**
- ✅ 优势：Dograh 可视化编排+零平台费；Bolna 配置驱动起步快；Vocode 模块化思路好。
- ❌ 不用：Dograh **目前仅英文**；Bolna 在找维护者；Vocode 自 2024-11 起基本停更。成熟度不足以承载交付。

### LiveKit 自身的已知弱点（答辩要主动讲）
- ~50 路并发时 SIP 接入延迟陡增（issue #3685）；Build 档冷启动 10–20s（需预热 worker，否则威胁 25 秒预算）；worker 负载均衡 0.5s 窗口竞态（#4884）；通用 ASR 对中文同音字（四/十）易混——**必须显式配中文 ASR**。
- 这些弱点我们都有对策：自托管+预热、显式 zh 模型、provider 可换。**知道框架的坑并有对策，本身就是工程品味的证明。**

---

## 2. 托管 SaaS 对比（为什么不用 Vapi/Retell 们）

| 平台 | 价格（全包/分钟） | 真实延迟 | 中文 | 锁定风险 |
|---|---|---|---|---|
| Vapi | ~$0.15–0.33（含 $0.05 平台费） | 标称<500ms，**实测高载 800ms–5s** | 列了支持，无独立中文测评 | **高**（私有 JSON schema） |
| Retell | ~$0.07–0.31 | 实测 ~600ms，barge-in <700ms | 普通话支持较好 | 中（编排层私有） |
| Bland | $0.09–0.14 + $299/月起 | 800ms–2.5s | 弱（未列为强项） | 中高（Pathways 私有） |
| Inworld | TTS 按字符计费 | TTS <100ms（2026 实时榜第一） | 取决于自接 ASR | 低（但非整机方案） |
| PolyAI/Cresta | 企业合同（~$150k/年起） | — | — | 很高 |

**SaaS 的真实优势**：几分钟出 demo、电话号码托管、barge-in 调好、无 DevOps。**如果这是一个"周五下班前要 demo"的任务，Vapi/Retell 是对的。**

**为什么不用**：
1. **这道题打分的就是技术选型与自建能力**——用 SaaS 等于把被考察的部分外包了，答辩故事变成"我会配置平台"；
2. **锁定**：工作流/编排是平台私有格式，迁移=重写；我们的 agent 逻辑是纯 Python，可测试可迁移；
3. **成本曲线**：规模化后（>10 万分钟/月）自托管约 $0.03/分钟 vs 平台 $0.10–0.15，差 60–80%；
4. **中文掌控力**：平台的中文质量取决于它接了谁，我们无法换到阿里/讯飞/MiniMax 这类中文最优 provider。

**正确的工程姿势（也是答辩答案）**：业务验证期用托管平台几天出活是合理的；量级和质量要求一旦确立，转自托管框架。本题直接考后者，所以直接做后者。

---

## 3. 电话原生 / 云直连方案（为什么不绕过框架直连）

| 方案 | 优势 | 为什么不用 |
|---|---|---|
| **Twilio ConversationRelay** | Twilio 号到 LLM 最顺滑；托管 barge-in；p50<500ms | +$0.07/分钟编排费；**深度锁定 Twilio**；中文取决于其合作 STT/TTS（不保证普通话同等质量） |
| **OpenAI Realtime + SIP 直连** | 单一供应商、跳数最少；gpt-realtime 原生中文 | **SIP 并发/故障转移/扩缩全要自己扛**（没有媒体服务器层）；整栈锁死 OpenAI；复杂打断场景要自写 |
| **Gemini Live / Vertex** | 90+ 语言、中途切语言；音频直进直出 | **没有原生 SIP**，仍需电话桥（绕回 LiveKit/Twilio）；电话路径文档少；中国大陆受限 |
| **Amazon Nova Sonic / Connect** | 电话平台原生、合规强 | **不支持中文**（七种语言无中文）——直接出局 |
| **阿里云 ISI / 火山引擎豆包** | **中文质量最佳**；CosyVoice/豆包口语化强 | 美国个人开户摩擦大（实名/验证）；**电话接入要完全 DIY**（无 SIP 编排）；作为 LiveKit 的 **TTS/STT 插件**接入才是正确用法 |

**框架层（LiveKit）给我们的，恰是这些方案都不给的**：电话+打断+并发的抽象 **加上** provider 全可换。直连云栈 = 要么把并发工程扛回自己身上（OpenAI SIP），要么换一个更深的锁定（ConversationRelay），要么根本没电话层（Gemini）。**中文最优资源（阿里/火山）正确的接法是作为 LiveKit 插件，而不是替代 LiveKit。**

---

## 4. 决策矩阵（按本任务的权重）

| 标准（权重） | LiveKit | Pipecat | TEN | Vapi/Retell | OpenAI SIP 直连 |
|---|---|---|---|---|---|
| 7 天交付（30%） | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 像真人/打断（20%） | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| 中文质量可控（20%） | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| 答辩可辩护（15%） | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| 无锁定/成本（15%） | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| **加权** | **4.7** | 3.9 | 3.7 | 3.1 | 2.8 |

## 5. 后续 A/B 计划（已列入 CHANGELOG 计划池）
1. **中文音色 A/B**：OpenAI TTS vs Azure zh-CN vs MiniMax/CosyVoice2（providers 已留好开关）；
2. **TEN 转向检测对照**：若中文 turn-taking 实测不满意，单独对照 TEN VAD；
3. **Pipecat 对照**：MVP 验证后做一轮部署/掌控力对比；
4. **生产中文栈**：阿里 Paraformer STT + CosyVoice TTS 以 LiveKit 插件形态接入。

---

## Sources（按主题）

**开源框架**：[LiveKit Agents GitHub](https://github.com/livekit/agents) · [LiveKit latency blog](https://livekit.com/blog/understand-and-improve-agent-latency) · [LiveKit telephony docs](https://docs.livekit.io/telephony/) · [issue #3685](https://github.com/livekit/agents/issues/3685) · [issue #4884](https://github.com/livekit/agents/issues/4884) · [Pipecat GitHub](https://github.com/pipecat-ai/pipecat) · [Pipecat Cloud GA](https://www.daily.co/blog/pipecat-cloud-is-now-generally-available/) · [Pipecat 生产并发实践](https://luonghongthuan.com/en/blog/pipecat-voice-agent-production-scalable-guide/) · [TEN Framework](https://github.com/TEN-framework/ten-framework) · [TEN Turn Detection](https://github.com/TEN-framework/ten-turn-detection) · [Agora TEN VAD blog](https://www.agora.io/en/blog/making-voice-ai-agents-more-human-with-ten-vad-and-turn-detection/) · [Dograh](https://github.com/dograh-hq/dograh) · [Bolna](https://github.com/bolna-ai/bolna) · [Vocode](https://github.com/vocodedev/vocode-core)

**SaaS**：[Vapi pricing](https://vapi.ai/pricing) · [Vapi $500M valuation (TechCrunch)](https://techcrunch.com/2026/05/12/vapi-hits-500m-valuation-as-amazon-ring-chose-its-ai-platform-over-40-rivals/) · [Retell pricing](https://www.retellai.com/pricing) · [Retell review (Coval)](https://www.coval.ai/blog/retell-ai-review-2026-features-pricing-and-when-to-use-it) · [Bland pricing (Emitrr)](https://emitrr.com/blog/bland-ai-pricing/) · [Inworld pricing](https://inworld.ai/pricing) · [自托管 vs Vapi TCO (Dograh)](https://blog.dograh.com/self-hosted-voice-agents-vs-vapi-real-cost-analysis-tco-break-even/) · [Vapi vs LiveKit (Samcom)](https://www.samcomtechnologies.com/blog/vapi-vs-livekit-for-ai-voice-agents-in-2026-a-developer-head-to-head)

**电话原生/云**：[Twilio ConversationRelay](https://www.twilio.com/en-us/products/conversational-ai/conversationrelay) · [OpenAI Realtime SIP docs](https://developers.openai.com/api/docs/guides/realtime-sip) · [gpt-realtime](https://openai.com/index/introducing-gpt-realtime/) · [Gemini Live API](https://ai.google.dev/gemini-api/docs/live-api) · [Nova Sonic 语言支持](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-language-support.html) · [阿里云 ISI](https://www.alibabacloud.com/en/product/intelligent-speech-interaction) · [CosyVoice TTS](https://www.alibabacloud.com/help/en/model-studio/text-to-speech) · [火山引擎国际接入](https://tokenmix.ai/blog/doubao-api-international-access-guide-2026) · [WebRTC.ventures 框架选型](https://webrtc.ventures/2026/03/choosing-a-voice-ai-agent-production-framework/)
