"""Build the STT / LLM / TTS components from config.

Keeping construction here (instead of inline in agent.py) is what makes the
stack swappable: to evaluate a different Chinese TTS (MiniMax, Azure zh-CN,
Qwen3-TTS) or a different LLM, add a branch here and flip an env var — the agent
pipeline never changes.
"""

from __future__ import annotations

from .config import Settings


def build_stt(cfg: Settings):
    if cfg.stt_provider == "openai":
        from livekit.plugins import openai

        return openai.STT(
            model=cfg.stt_model,
            language=cfg.stt_language,
            api_key=cfg.openai_api_key or None,
        )
    raise ValueError(f"Unsupported STT_PROVIDER: {cfg.stt_provider}")


def build_llm(cfg: Settings):
    if cfg.llm_provider == "anthropic":
        from livekit.plugins import anthropic

        # Haiku 4.5: fast, cheap, strong Chinese + tool calling, no thinking
        # (lowest latency for a voice turn). Tool calling drives slot-filling.
        return anthropic.LLM(
            model=cfg.llm_model,
            api_key=cfg.anthropic_api_key or None,
        )
    if cfg.llm_provider == "openai":
        from livekit.plugins import openai

        return openai.LLM(model=cfg.llm_model, api_key=cfg.openai_api_key or None)
    raise ValueError(f"Unsupported LLM_PROVIDER: {cfg.llm_provider}")


def build_tts(cfg: Settings):
    if cfg.tts_provider == "openai":
        from livekit.plugins import openai

        return openai.TTS(
            model=cfg.tts_model,
            voice=cfg.tts_voice,
            api_key=cfg.openai_api_key or None,
            # Nudge the voice toward natural, warm Mandarin.
            instructions="用自然、热情、口语化的中文普通话说话，像一个干练友好的门卫。",
        )
    raise ValueError(f"Unsupported TTS_PROVIDER: {cfg.tts_provider}")


def build_vad():
    from livekit.plugins import silero

    return silero.VAD.load()


def build_turn_detection():
    """Multilingual (incl. Chinese) semantic turn detector for natural barge-in."""
    from livekit.plugins.turn_detector.multilingual import MultilingualModel

    return MultilingualModel()
