"""Build the STT / LLM / TTS components from config.

Keeping construction here (instead of inline in agent.py) is what makes the
stack swappable: to evaluate a different Chinese TTS (Azure zh-CN, MiniMax,
Qwen3-TTS) or STT (Deepgram, Paraformer), add a branch here and flip an env var
— the agent pipeline never changes.

Optional providers use lazy imports + `pip install livekit-plugins-<x>`; the
default OpenAI path needs nothing extra.
"""

from __future__ import annotations

from .config import Settings


def build_stt(cfg: Settings):
    if cfg.stt_provider == "openai":
        from livekit.plugins import openai

        kwargs = {"model": cfg.stt_model, "language": cfg.stt_language}
        if cfg.openai_api_key:  # only override env when explicitly set
            kwargs["api_key"] = cfg.openai_api_key
        return openai.STT(**kwargs)
    if cfg.stt_provider == "deepgram":
        # Chinese ASR upgrade. Needs: pip install livekit-plugins-deepgram
        from livekit.plugins import deepgram

        return deepgram.STT(model=cfg.stt_model or "nova-2", language=cfg.stt_language)
    raise ValueError(f"Unsupported STT_PROVIDER: {cfg.stt_provider}")


def build_llm(cfg: Settings):
    if cfg.llm_provider == "openai":
        from livekit.plugins import openai

        kwargs = {"model": cfg.llm_model}
        if cfg.openai_api_key:
            kwargs["api_key"] = cfg.openai_api_key
        return openai.LLM(**kwargs)
    if cfg.llm_provider == "anthropic":
        from livekit.plugins import anthropic

        # Claude Haiku 4.5: fast, cheap, strong Chinese + tool calling, no
        # thinking (lowest latency for a voice turn). Drives slot-filling.
        kwargs = {"model": cfg.llm_model}
        if cfg.anthropic_api_key:
            kwargs["api_key"] = cfg.anthropic_api_key
        return anthropic.LLM(**kwargs)
    raise ValueError(f"Unsupported LLM_PROVIDER: {cfg.llm_provider}")


def build_tts(cfg: Settings):
    if cfg.tts_provider == "openai":
        from livekit.plugins import openai

        kwargs = {
            "model": cfg.tts_model,
            "voice": cfg.tts_voice,
            # Nudge the voice toward natural, warm Mandarin.
            "instructions": "用自然、热情、口语化的中文普通话说话，像一个干练友好的门卫。",
        }
        if cfg.openai_api_key:
            kwargs["api_key"] = cfg.openai_api_key
        return openai.TTS(**kwargs)
    if cfg.tts_provider == "azure":
        # Best-supported Chinese TTS upgrade (zh-CN neural voices).
        # Needs: pip install livekit-plugins-azure ; AZURE_SPEECH_KEY/REGION env.
        from livekit.plugins import azure

        return azure.TTS(voice=cfg.tts_voice or "zh-CN-XiaoxiaoNeural")
    raise ValueError(f"Unsupported TTS_PROVIDER: {cfg.tts_provider}")


def build_vad():
    from livekit.plugins import silero

    return silero.VAD.load()


def build_turn_detection():
    """Multilingual (incl. Chinese) semantic turn detector for natural barge-in."""
    from livekit.plugins.turn_detector.multilingual import MultilingualModel

    return MultilingualModel()
