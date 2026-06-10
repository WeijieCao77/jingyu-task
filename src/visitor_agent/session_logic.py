"""Provider-agnostic registration brain shared by the live agent and the sim.

`RegistrationSession` owns the slot state and the two actions the LLM can take
(`record` / `complete`). The LiveKit agent wraps these as @function_tool methods;
the offline simulator wraps the same two methods in an Anthropic tool-use loop.
One source of truth for behaviour → the simulator genuinely exercises the same
logic the phone call will.

Notifiers are pluggable (`Notifier` protocol): the live notifier writes the DB
row and pushes the WeCom card; the mock notifier just records the call. The
returning-visitor lookup is injected as a plain callable so the core has no hard
dependency on the database and stays unit-testable.
"""

from __future__ import annotations

from typing import Awaitable, Callable, Protocol

from .slots import VisitorInfo


class Notifier(Protocol):
    async def notify(self, info: dict) -> str:
        """Persist + push the completed visit; return the guard's confirm URL."""
        ...


LookupReturning = Callable[[str], dict | None]
# (kind, role, text, payload) -> None   — optional dashboard event sink
EventSink = Callable[[str, str | None, str | None, dict | None], None]


class RegistrationSession:
    def __init__(
        self,
        notifier: Notifier,
        lookup_returning: LookupReturning | None = None,
        tz: str = "Asia/Shanghai",
        event_sink: EventSink | None = None,
    ) -> None:
        self.info = VisitorInfo()
        self.notifier = notifier
        self.lookup_returning = lookup_returning
        self.tz = tz
        self.event_sink = event_sink
        self.completed = False
        self.returning_match: dict | None = None

    def _emit(self, kind: str, text: str | None = None, payload: dict | None = None) -> None:
        if self.event_sink:
            try:
                self.event_sink(kind, None, text, payload)
            except Exception:  # noqa: BLE001 — dashboard must never break the call
                pass

    # ---- tool 1: record (incremental, called as info arrives) ----
    def record(
        self,
        plate: str | None = None,
        company: str | None = None,
        reason: str | None = None,
        phone: str | None = None,
    ) -> str:
        plate_was_unknown = self.info.plate is None
        self.info.update(plate=plate, company=company, reason=reason, phone=phone)

        hint = ""
        if (
            self.info.plate
            and plate_was_unknown
            and self.lookup_returning
            and self.returning_match is None
        ):
            prev = self.lookup_returning(self.info.plate)
            if prev:
                self.returning_match = prev
                if not self.info.company and prev.get("company"):
                    self.info.company = prev["company"]
                if not self.info.reason and prev.get("reason"):
                    self.info.reason = prev["reason"]
                hint = (
                    " 【回访车辆】该车牌历史记录：单位="
                    f"{prev.get('company')}，事由={prev.get('reason')}。"
                    "请直接向访客确认是否与上次相同，不要从头重问。"
                )

        recorded = self.info.human_summary() or "（暂无）"
        missing = self.info.missing_labels_zh()
        missing_str = "、".join(missing) if missing else "无，信息已齐"
        result = f"已记录：{recorded}。还缺：{missing_str}。{hint}".strip()
        self._emit("slot", text=result, payload=self.info.to_dict())
        return result

    # ---- tool 2: complete (validate, persist, push to guard) ----
    async def complete(self) -> str:
        missing = self.info.missing_labels_zh()
        if missing:
            return f"信息还不全，还差：{'、'.join(missing)}。请先补齐再调用完成登记。"

        self.info.stamp_entry_time(self.tz)
        payload = self.info.to_dict()
        payload["returning"] = bool(self.returning_match)
        confirm_url = await self.notifier.notify(payload)
        self.completed = True
        self._emit("completed", text=self.info.human_summary(), payload=payload)
        self._emit("pushed", text="已推送门卫企业微信", payload={"confirm_url": confirm_url})
        return (
            f"登记完成，已通知门卫。请向访客复述并请其稍等放行："
            f"{self.info.human_summary()}。"
        )


# ----------------------------------------------------------------------------
# Notifier implementations
# ----------------------------------------------------------------------------


class MockNotifier:
    """Used by the simulator and unit tests — no network, records calls."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def notify(self, info: dict) -> str:
        from .notify.wecom import build_markdown

        url = "https://demo.local/confirm?token=MOCK_TOKEN"
        self.calls.append(info)
        print("\n[WECOM 模拟推送]\n" + build_markdown(info, url) + "\n")
        return url


class LiveNotifier:
    """Real path: write the DB row, then push the WeCom card with a confirm link."""

    def __init__(self, settings) -> None:
        self.s = settings

    async def notify(self, info: dict) -> str:
        import secrets

        from .db import repo
        from .notify import dispatch

        token = secrets.token_urlsafe(16)
        repo.create_visit(info, confirm_token=token, status="pending")
        confirm_url = f"{self.s.public_base_url.rstrip('/')}/confirm?token={token}"
        await dispatch.push(self.s, info, confirm_url)
        return confirm_url


def make_db_lookup() -> LookupReturning:
    """Returning-visitor lookup backed by the DB (used in the live path)."""
    from .db import repo

    def _lookup(plate: str) -> dict | None:
        visit = repo.find_recent_visit_by_plate(plate)
        return visit.to_dict() if visit else None

    return _lookup
