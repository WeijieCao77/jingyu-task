"""Central, env-driven configuration.

Every provider choice (STT / LLM / TTS) and external endpoint is read from the
environment so the same code runs the v1 stack today and a different stack
tomorrow with only a `.env` change — no edits to the pipeline code.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ---- LLM brain ----
    # 默认全 OpenAI（只需一个 key 把线路跑通）；想用 Claude 当大脑改成 anthropic。
    llm_provider: str = "openai"             # openai | anthropic
    llm_model: str = "gpt-4o-mini"           # anthropic 时用 claude-haiku-4-5
    anthropic_api_key: str = ""

    # ---- STT ----
    stt_provider: str = "openai"
    stt_model: str = "gpt-4o-transcribe"
    stt_language: str = "zh"

    # ---- TTS ----
    tts_provider: str = "openai"
    tts_model: str = "gpt-4o-mini-tts"
    tts_voice: str = "alloy"
    openai_api_key: str = ""

    # ---- Guard notification channel ----
    # "none" = 保安直接在 Dashboard 上点确认（零账号，默认）。
    # 也可 discord / telegram（美国可用，需各自账号）；wecom 为生产渠道。
    notify_channel: str = "none"             # none | discord | telegram | wecom
    discord_webhook_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    wecom_webhook_url: str = ""

    # ---- Confirm web server ----
    public_base_url: str = "http://localhost:8080"
    web_port: int = 8080

    # ---- Database ----
    database_url: str = "sqlite:///./data/visits.db"

    # ---- LiveKit ----
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    # ---- Latency tuning (lower = faster responses, slightly more risk of
    #      cutting the speaker off; tune per real-world testing) ----
    preemptive_generation: bool = True       # start LLM before turn fully ends
    vad_min_silence: float = 0.4             # silero endpoint silence (s)
    min_endpointing_delay: float = 0.4       # how long to wait before replying

    # ---- Gate barrier (Hikvision ISAPI). Leave URL empty = stub for demo. ----
    hikvision_url: str = ""                   # e.g. http://192.168.1.64
    hikvision_user: str = "admin"
    hikvision_password: str = ""
    hikvision_channel: int = 1

    # ---- Company roster matching (来访单位 自动纠正到园区名单) ----
    # 留空=关闭（不影响基础 demo）。指向一个 JSON 名单文件即开启。
    roster_path: str = ""
    roster_threshold: float = 0.55

    # ---- Misc ----
    timezone: str = "Asia/Shanghai"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
