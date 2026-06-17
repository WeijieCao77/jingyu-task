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
        # Any OpenAI-compatible endpoint (OpenRouter / DashScope-compat / DeepSeek
        # / Moonshot / Volcengine ...) → the customer can pick *any* model.
        if cfg.llm_base_url:
            kwargs["base_url"] = cfg.llm_base_url
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


def build_vad(cfg: Settings | None = None):
    from livekit.plugins import silero

    min_silence = cfg.vad_min_silence if cfg else 0.4
    return silero.VAD.load(min_silence_duration=min_silence)


def _env_flag(name: str, default: str = "0") -> bool:
    import os

    return os.getenv(name, default).lower() in ("1", "true", "yes")


def realtime_allow_interrupt() -> bool:
    """Barge-in toggle. Default off: the AI finishes its sentence (the recommended
    setting for phone lines, where echo/noise would otherwise cut it off)."""
    return _env_flag("REALTIME_ALLOW_INTERRUPT", "0")


def realtime_server_vad() -> bool:
    """Whether to use OpenAI's *server-side* turn detection (default off).

    Off (default) → local silero VAD on the AgentSession drives turns; see
    build_realtime for why this is the safe default on telephony. On → legacy
    server-side VAD (only sound with real echo cancellation)."""
    return _env_flag("REALTIME_SERVER_VAD", "0")


def build_realtime(cfg: Settings):
    """Speech-to-speech realtime model (low latency). Still transcribes the
    caller (for slot-filling / dashboard / DB) and supports tool calling.
    Uses the OpenAI key (OPENAI_API_KEY in env)."""
    from livekit.plugins import openai

    kwargs: dict = {"model": cfg.realtime_model, "voice": cfg.realtime_voice}
    if cfg.openai_api_key:
        kwargs["api_key"] = cfg.openai_api_key
    # Keep a Chinese transcript of the caller's audio so the rest of the system
    # (record_visitor_info, dashboard, visits DB) works exactly as in pipeline mode.
    try:
        from openai.types.beta.realtime.session import InputAudioTranscription

        kwargs["input_audio_transcription"] = InputAudioTranscription(
            model=cfg.stt_model, language=cfg.stt_language
        )
    except Exception:  # noqa: BLE001 — type path varies by SDK; transcript is best-effort
        pass
    import os  # local import → avoids touching module top (smaller merge surface)

    # Turn-taking. DEFAULT: disable OpenAI's server-side VAD (turn_detection=None)
    # and let the AgentSession's local silero VAD drive turns. WHY this is the
    # default on a phone line: the AI's own audio echoes back through the handset,
    # and OpenAI's server VAD hears that echo as "the caller talking" → ends a
    # phantom turn → create_response fires a reply to the echo. The AI ends up
    # talking to itself before the visitor ever answers (the realtime "自说自话"
    # bug). With server VAD off, livekit-agents (a) discards inbound audio while the
    # AI is mid-utterance — only possible with allow_interruptions=False, which
    # server-side turn detection forbids — so the echo never reaches the model, and
    # (b) commits the buffer + replies on the LOCAL VAD's end-of-turn. The phone
    # echo therefore can't become a turn. Reproduced + verified with an echo-loopback
    # probe (15 self-talk bursts → 1). REALTIME_SERVER_VAD=1 restores server-side
    # detection (only safe with real echo cancellation, e.g. a browser mic w/ AEC).
    if realtime_server_vad():
        try:
            from openai.types.beta.realtime.session import TurnDetection

            kwargs["turn_detection"] = TurnDetection(
                type="server_vad",
                threshold=float(os.getenv("REALTIME_VAD_THRESHOLD", "0.8")),
                prefix_padding_ms=300,
                silence_duration_ms=int(os.getenv("REALTIME_SILENCE_MS", "800")),
                create_response=True,
                interrupt_response=realtime_allow_interrupt(),
            )
        except Exception:  # noqa: BLE001 — SDK field variance; defaults still work
            pass
    else:
        # Explicit None → session.update sends `turn_detection: null`, which truly
        # disables OpenAI server VAD (verified: the field serializes, not omitted).
        kwargs["turn_detection"] = None
    # Noise reduction must match the mic: near_field = phone handset / headset
    # (the call case here); far_field = laptop / conference-room mic. The wrong
    # mode distorts speech. REALTIME_NOISE_REDUCTION=off disables it entirely.
    _nr = os.getenv("REALTIME_NOISE_REDUCTION", "near_field").lower()
    if _nr in ("near_field", "far_field"):
        try:
            from openai.types.beta.realtime.session import InputAudioNoiseReduction

            kwargs["input_audio_noise_reduction"] = InputAudioNoiseReduction(type=_nr)
        except Exception:  # noqa: BLE001
            pass
    return openai.realtime.RealtimeModel(**kwargs)


def build_turn_detection():
    """Multilingual (incl. Chinese) semantic turn detector for natural barge-in."""
    from livekit.plugins.turn_detector.multilingual import MultilingualModel

    return MultilingualModel()
