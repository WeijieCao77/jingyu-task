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
    llm_provider: str = "anthropic"          # anthropic | openai
    llm_model: str = "claude-haiku-4-5"
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
    # demo 用 discord / telegram（美国可用）；生产用 wecom（企业微信）
    notify_channel: str = "discord"          # discord | telegram | wecom
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

    # ---- Misc ----
    timezone: str = "Asia/Shanghai"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
