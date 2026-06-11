# 语音架构 A/B：Pipeline vs Speech-to-Speech（提速实验）

> 现象：现在说一句话 / 让 AI 说话会"卡一会"。主因是 **Pipeline 三段串联**（STT→LLM→TTS）。
> 本分支加了一个开关，**不换框架（还是 LiveKit）**，只把"大脑"换成 speech-to-speech 实时模型，
> 你在真机上 A/B 对比延迟与中文准确度。

## 两种模式

| | `VOICE_MODE=pipeline`（可回退） | `VOICE_MODE=realtime`（**默认**·真机更快） |
|---|---|---|
| 链路 | STT → LLM → TTS（三段串联，延迟叠加） | 一个实时模型，音频进音频出 |
| 延迟 | 较高（你感觉到的"卡"） | **明显更低**（几乎无停顿） |
| 框架 | LiveKit | **还是 LiveKit**（只换 `llm`=RealtimeModel） |
| 文字转写 | 有 | **仍有**（`input_audio_transcription` zh）→ 填槽/后台/数据库不变 |
| 工具调用 | 有 | **仍有**（填槽、转人工不变） |
| 密钥 | OpenAI | **同一个 OPENAI_API_KEY**，零新账号 |
| 成本/分钟 | ~$0.02–0.06 | ~$0.18–0.46（demo 可接受） |
| 中文准确度 | 取决于 STT，数字易错 | 对话式更强；数字仍靠 **AI 确认层** 兜底 |

## 怎么切换 / A/B
```
# .env
VOICE_MODE=realtime          # 想提速就切这个；改回 pipeline 即恢复
REALTIME_MODEL=gpt-realtime
REALTIME_VOICE=marin         # 试不同音色
```
重启 agent worker，打开 `/voice` 说话，对比：① 回应是否还"卡" ② 中文/数字识别准不准。
切回 `VOICE_MODE=pipeline` 再测一遍，挑你这台机器/网络下更好的。

## 实现说明（保留可回退）
- `providers.build_realtime()` 构造 `openai.realtime.RealtimeModel`（带 zh 转写）。
- `agent.py` 按 `VOICE_MODE` 分支：realtime 时 `AgentSession(llm=RealtimeModel)`，不接 STT/TTS/VAD（实时模型自带服务端 turn detection）；pipeline 保持原样（含 preemptive_generation + VAD 调优）。
- **默认 realtime（v0.23，真机 A/B 后定）**；`VOICE_MODE=pipeline` 一行回退（便宜/有文字/不需 gpt-realtime 权限）。

## 还想再快 / 再准的其他杠杆
- **Pipeline 内提速**（不换模式）：已开 `preemptive_generation`、调低 `VAD_MIN_SILENCE`/`MIN_ENDPOINTING_DELAY`；可继续下调。
- **中文 ASR 更准**（pipeline）：`STT_PROVIDER=deepgram`（zh）或 Azure；生产可上阿里 Paraformer。
- **Realtime 音色**：`REALTIME_VOICE` 换一个更自然的；或评估 Gemini Live（需另接）。
- **数字准确**：无论哪种模式，**AI 复述确认层**（车牌逐位、手机分组）都在生效，是兜底。

> 诚实提醒：realtime 模式在本仓库**未经真机验证**（沙箱无音频/网络）。请你真机 A/B；若 realtime 有问题，改回 `VOICE_MODE=pipeline` 即可，主流程不受影响。
