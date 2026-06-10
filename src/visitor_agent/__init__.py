"""Visitor Voice Agent — an end-to-end Chinese phone-based visitor-registration agent.

Pipeline (v1): OpenAI STT (zh) -> Claude Haiku 4.5 (slot-filling) -> OpenAI TTS,
orchestrated by LiveKit Agents over a Twilio SIP phone number. Structured visitor
info is pushed to a WeCom (企业微信) group bot; the guard confirms via a tokenized
link, which triggers the (stubbed) gate-open command.
"""

__version__ = "0.1.0"
