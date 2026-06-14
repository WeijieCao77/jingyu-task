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

    # ---- Voice architecture ----
    # realtime = speech-to-speech 实时模型（默认；真机实测首句 ≈1.4s，明显更快）；
    # pipeline = STT→LLM→TTS（便宜、有文字，可回退）。客户可一行切换。
    voice_mode: str = "realtime"             # realtime | pipeline
    realtime_model: str = "gpt-realtime"
    realtime_voice: str = "marin"

    # ---- LLM brain ----
    # 默认全 OpenAI（只需一个 key 把线路跑通）；想用 Claude 当大脑改成 anthropic。
    llm_provider: str = "openai"             # openai | anthropic
    llm_model: str = "gpt-4o-mini"           # anthropic 时用 claude-haiku-4-5
    anthropic_api_key: str = ""
    # 客户想用"任意模型"时：把 LLM_BASE_URL 指向任一 OpenAI 兼容端点
    # （OpenRouter / 阿里 DashScope-compat / DeepSeek / Moonshot / 火山 等），
    # LLM_MODEL 填该端点的模型名，OPENAI_API_KEY 填该端点的 key。留空=用官方 OpenAI。
    llm_base_url: str = ""
    # 模型分层：门卫数据查询 Agent 可用与对话大脑不同的模型（留空=同 LLM_MODEL）。
    # 查询要"会用工具、算时间范围"，可上稍强模型；省钱也可保持便宜模型。
    guard_query_model: str = ""

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
    notify_channel: str = "none"             # none | discord | telegram | wecom | wecom_app | pushplus
    discord_webhook_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    wecom_webhook_url: str = ""              # 企业微信「群机器人」webhook（需先有普通群）
    # 企业微信「自建应用」API（NOTIFY_CHANNEL=wecom_app）：不用建群，直接发给成员、收在
    # 企业微信 App。三值从 work.weixin.qq.com 管理后台取（我的企业 / 应用管理→自建应用）。
    wecom_corp_id: str = ""                  # 企业ID corpid
    wecom_agent_id: str = ""                 # 自建应用 AgentId
    wecom_app_secret: str = ""              # 自建应用 Secret
    # 备选渠道：PushPlus → 个人微信（NOTIFY_CHANNEL=pushplus）。关注 pushplus 公众号拿 token。
    pushplus_token: str = ""

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

    # ---- 「常客名单」 / 黑名单 (access list；按车牌/手机精确匹配) ----
    # 这是访客侧的「常客名单」——和下面电话侧的「门卫查询名单 GUARD_PHONES」是
    # 两套完全不同的东西，别混（前者识别老客户/VIP，后者识别门卫本人来查数据）。
    # 留空=关闭。指向 JSON 文件即开启（见 access.demo.json）。文件里：
    #   whitelist = 常客（已知客户/VIP，快速通道）；blacklist = 黑名单（告警，绝不自动放行）。
    access_list_path: str = ""
    # 常客是否自动放行（跳过保安、直接抬杆）。默认 False=仍由保安点放行，只是卡片标注「常客」。
    auto_pass_whitelist: bool = False

    # ---- Guard-only access (数据查询/后台仅门卫可用，访客不能查) ----
    # 网页端：设了 GUARD_ACCESS_KEY 后，/dashboard /ask /admin 及数据 API 需先在 /login
    #   输入这个口令（留空=不设防，demo 方便）。
    guard_access_key: str = ""
    # 电话端「门卫查询名单」：门卫自己的手机号（逗号分隔 1~2 个）。来电号码在此名单
    #   = 门卫本人 → 转「语音数据助手」问数据；否则=访客，走登记。留空=所有来电按访客。
    #   注意：这是门卫的查询入口名单，跟上面访客侧的「常客名单」(access list) 完全不同，别混。
    guard_phones: str = ""
    # 转人工外呼：系统拨这个门卫号码、把他接进当前通话（电话原生介入，AI 让位）。
    guard_dial_number: str = ""            # 门卫手机号 E.164
    sip_outbound_trunk_id: str = ""        # LiveKit 出站 SIP trunk id（ST_...）；见 TELEPHONY.md

    # ---- Multi-tenant (productization)；留空=单租户（现状不变） ----
    # 指向 tenants.json 即开启：按被叫号码路由到各租户独立的名单/通知/门卫配置。
    tenants_path: str = ""

    # ---- Call lifecycle (auto end the call so the line doesn't stay open) ----
    # 登记完成并道别后，若访客 N 秒无新发言 → agent 主动挂断；0=不自动挂断。
    hangup_silence_sec: float = 6.0
    # 单通电话最长时长（秒）兜底，防异常常开；0=不限制。
    max_call_sec: int = 180

    # ---- Misc ----
    timezone: str = "Asia/Shanghai"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
