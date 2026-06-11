# 模型可换架构（现在用哪个 / 怎么换 / 客户可选任意模型）

> 需求：最终落地用哪个模型由客户决定，所以要"随时换不同模型"。本项目**就是为换模型设计的**——
> 所有模型都在 `.env` 配（`providers.py` 是唯一装配点），改 env 即换，**不动代码、不重写**。

## 1. 现在用的模型（默认）

| 环节 | 默认模型 | 配置项 |
|---|---|---|
| 大脑 LLM | `gpt-4o-mini`（OpenAI） | `LLM_PROVIDER` / `LLM_MODEL` / `LLM_BASE_URL` |
| 听 STT | `gpt-4o-transcribe`（OpenAI, zh） | `STT_PROVIDER` / `STT_MODEL` / `STT_LANGUAGE` |
| 说 TTS | `gpt-4o-mini-tts`（OpenAI） | `TTS_PROVIDER` / `TTS_MODEL` / `TTS_VOICE` |
| 语音架构 | pipeline（三段）；可切 realtime（speech-to-speech，`gpt-realtime`） | `VOICE_MODE` / `REALTIME_MODEL` |

## 2. 换 LLM 大脑

### 2a. 换 OpenAI 系（同厂不同模型）
```
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o          # 或 gpt-4o-mini / gpt-4.1 / o4-mini ...
```
### 2b. 换 Claude
```
LLM_PROVIDER=anthropic
LLM_MODEL=claude-haiku-4-5    # 或其他 Claude 型号
ANTHROPIC_API_KEY=sk-ant-...
```
### 2c. 换"任意模型"（客户最终决定时，最关键）
把 `LLM_BASE_URL` 指向**任一 OpenAI 兼容端点**，`LLM_MODEL` 填该端点的模型名，`OPENAI_API_KEY` 填该端点的 key——
一套配置即可接 GPT / Claude / Gemini / Qwen / Llama / DeepSeek / 豆包 / Kimi 等几乎任意模型，**包括国内模型**：

| 想用 | LLM_BASE_URL | LLM_MODEL 示例 |
|---|---|---|
| OpenRouter（聚合，几百个模型） | `https://openrouter.ai/api/v1` | `anthropic/claude-3.5-sonnet`、`google/gemini-2.0-flash`、`qwen/qwen-2.5-72b-instruct`、`deepseek/deepseek-chat` |
| 阿里 Qwen（DashScope 兼容） | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus`、`qwen-max` |
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` |
| Moonshot / Kimi | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| 火山引擎豆包（方舟兼容） | 火山方舟的 compatible URL | 你的 endpoint/模型 id |

> 原理：LiveKit 的 openai 插件支持 `base_url`，凡是 **OpenAI Chat Completions 兼容**的端点都能直接接，且**工具调用（填槽/转人工）照常**——只要该模型支持 function calling。

## 3. 换 STT（听）
```
STT_PROVIDER=openai            # 默认；STT_MODEL=gpt-4o-transcribe
# 升级中文识别：
STT_PROVIDER=deepgram          # 需 pip install livekit-plugins-deepgram
# 生产可加阿里 Paraformer 等（在 providers.build_stt 加一支分支即可）
```

## 4. 换 TTS（说）
```
TTS_PROVIDER=openai            # 默认
TTS_PROVIDER=azure             # zh-CN 神经语音更自然；需 livekit-plugins-azure + AZURE_SPEECH_KEY/REGION
TTS_VOICE=zh-CN-XiaoxiaoNeural
# 可加 MiniMax / CosyVoice / Qwen3-TTS（providers.build_tts 加分支）
```

## 5. 换语音架构（提速）
```
VOICE_MODE=realtime           # speech-to-speech（gpt-realtime），延迟更低
REALTIME_MODEL=gpt-realtime
```

## 6. 架构为什么"随时可换"
- **唯一装配点 `providers.py`**：`build_llm / build_stt / build_tts / build_realtime` 按 env 造对象，业务逻辑（对话/填槽/后台/数据库/转人工）与具体模型**完全解耦**。
- **加一个新厂商 = 加一支 `if provider == "xxx"` 分支**（几行），不碰其它任何代码。
- LLM 通过 `LLM_BASE_URL` 已能接**任意 OpenAI 兼容端点**，无需改码。
- 答辩口径：*"模型是配置项不是架构。客户选定后，改 .env 三五行即切换，包括切到国内模型。"*

## 7. 选型建议（给客户决策时参考）
- **要快**：`VOICE_MODE=realtime`（s2s）。
- **要中文最准/自然**：STT 上 Deepgram-zh/阿里 Paraformer，TTS 上 Azure zh-CN/MiniMax，LLM 上 Qwen/DeepSeek。
- **要省**：pipeline + gpt-4o-mini / 国内便宜模型。
- **要合规/国内落地**：LLM 用国内模型（DashScope/DeepSeek/豆包）、TTS 用国内、通知用企业微信（见 WECHAT_PLAN.md）。
