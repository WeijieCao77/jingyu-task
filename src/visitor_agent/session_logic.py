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

from typing import Callable, Protocol

from .slots import VisitorInfo


class Notifier(Protocol):
    async def notify(self, info: dict) -> str:
        """Persist + push the completed visit; return the guard's confirm URL."""
        ...


LookupReturning = Callable[[str | None, str | None], dict | None]
# (kind, role, text, payload) -> None   — optional dashboard event sink
EventSink = Callable[[str, str | None, str | None, dict | None], None]


class RegistrationSession:
    def __init__(
        self,
        notifier: Notifier,
        lookup_returning: LookupReturning | None = None,
        tz: str = "Asia/Shanghai",
        event_sink: EventSink | None = None,
        roster_match=None,  # Callable[[str|None], tuple[str|None, float]] | None
        access_check=None,  # Callable[[str|None, str|None], dict|None] | None
    ) -> None:
        self.info = VisitorInfo()
        self.notifier = notifier
        self.lookup_returning = lookup_returning
        self.tz = tz
        self.event_sink = event_sink
        self.roster_match = roster_match
        self.access_check = access_check
        self.completed = False
        self.escalated = False
        self.returning_match: dict | None = None
        self.access_match: dict | None = None

    @staticmethod
    def _returning_hint(prof: dict) -> str:
        basis = {
            "plate+phone": "车牌+手机均匹配，基本确定是本人本车",
            "phone": "手机号匹配，是本人（可能换了车）",
            "plate": "车牌匹配，是这辆车（可能换了司机，别假设同一人）",
        }.get(prof.get("match_type", ""), "历史匹配")
        who = prof.get("name") or "老客户"
        count = prof.get("visit_count") or 0
        freq = f"，累计第{count + 1}次来访" if count else ""
        last = f"上次：{prof.get('last_company') or '—'}／{prof.get('last_reason') or '—'}"
        return (
            f" 【回访识别·{basis}】{who}{freq}。{last}。"
            "请用一句话直接确认是否与上次相同（如『还是和上次一样来…吧？』），不要从头重问；"
            "若对方说不一样，再据实更新。"
        )

    @staticmethod
    def _returning_summary(prof: dict) -> str:
        """One-line returning-visitor tag for the card. The last-visit detail is
        shown on its OWN line (see common.status_lines), not crammed in here."""
        basis = {
            "plate+phone": "车牌+手机均匹配",
            "phone": "手机匹配·本人",
            "plate": "车牌匹配·同车",
        }.get(prof.get("match_type", ""), "历史匹配")
        who = prof.get("name") or "老访客"
        count = prof.get("visit_count") or 0
        nth = f"第{count + 1}次来" if count else ""
        parts = [who, basis] + ([nth] if nth else [])
        return " · ".join(parts)

    @staticmethod
    def _access_summary(m: dict) -> str:
        """One-line blacklist/whitelist summary for the card."""
        label = "⛔ 黑名单" if m.get("status") == "blacklist" else "✅ 常客"
        by = "车牌" if m.get("matched_on") == "plate" else "手机"
        parts = [label] + ([m["name"]] if m.get("name") else []) + (
            [m["reason"]] if m.get("reason") else []
        ) + [f"按{by}匹配"]
        return " · ".join(parts)

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
        name: str | None = None,
    ) -> str:
        prev_plate, prev_phone = self.info.plate, self.info.phone
        self.info.update(
            plate=plate, company=company, reason=reason, phone=phone, name=name
        )
        # Newly learned an identifier (plate or phone)?
        newly_identified = (self.info.plate and self.info.plate != prev_plate) or (
            self.info.phone and self.info.phone != prev_phone
        )

        hint = ""
        if self.lookup_returning and self.returning_match is None and newly_identified:
            prof = self.lookup_returning(self.info.plate, self.info.phone)
            if prof and prof.get("match_type"):
                self.returning_match = prof
                # Personalise + offer the prior visit for confirmation.
                if not self.info.name and prof.get("name"):
                    self.info.name = prof["name"]
                if not self.info.company and prof.get("last_company"):
                    self.info.company = prof["last_company"]
                if not self.info.reason and prof.get("last_reason"):
                    self.info.reason = prof["last_reason"]
                hint = self._returning_hint(prof)

        # Snap the company to the park roster (corrects mis-heard names). When a
        # roster IS configured but the company doesn't match anything, surface
        # that to the LLM so it can confirm once and, failing that, escalate
        # (FR-5: "公司不在园区名单" should be able to trigger 转人工).
        if company and self.roster_match and self.info.company:
            official, score = self.roster_match(self.info.company)
            if official and official != self.info.company:
                orig = self.info.company
                self.info.company = official
                hint += (
                    f" 【单位已匹配名单】把'{orig}'匹配到'{official}'，"
                    "请向访客确认是不是找这家。"
                )
            elif official is None:
                hint += (
                    f" 【单位不在园区名单】未找到'{self.info.company}'，先跟访客确认一次"
                    "（是否听错/换个说法）；仍对不上就转人工核实。"
                )

        # Phone sanity: a mainland mobile is 11 digits starting with 1. If what we
        # captured isn't, tell the LLM to re-confirm it (FR-8).
        from .slots import is_valid_cn_mobile

        if phone and self.info.phone and not is_valid_cn_mobile(self.info.phone):
            hint += (
                " 【手机号位数异常】这个号码不是11位/1开头，请向访客确认后重报手机号。"
            )

        # Blacklist / whitelist check on any newly-learned identifier. Kept out
        # of the AI-facing hint on purpose: the gatekeeper keeps registering
        # normally (no confrontation at the gate); the guard is the one alerted
        # via the card + dashboard. Blacklist can upgrade a prior whitelist hit.
        if self.access_check and newly_identified:
            m = self.access_check(self.info.plate, self.info.phone)
            if m and (self.access_match is None or m.get("status") == "blacklist"):
                self.access_match = m
                if m.get("status") == "blacklist":
                    self._emit(
                        "access_alert",
                        text=f"⛔ 黑名单访客：{m.get('reason') or '—'}",
                        payload={**self.info.to_dict(), **m},
                    )

        recorded = self.info.human_summary() or "（暂无）"
        missing = self.info.missing_labels_zh()
        missing_str = "、".join(missing) if missing else "无，信息已齐"
        result = f"已记录：{recorded}。还缺：{missing_str}。{hint}".strip()
        self._emit("slot", text=result, payload=self.info.to_dict())
        return result

    # ---- transfer to a human guard (escalation) ----
    def request_human(self, reason: str | None = None) -> str:
        """Flag that this call needs a real person; surfaces on the dashboard so
        the guard can join the same room (or call back the collected mobile)."""
        self.escalated = True
        self._emit(
            "escalation",
            text=f"请求转人工{('：' + reason) if reason else ''}",
            payload={**self.info.to_dict(), "reason": reason},
        )
        return "好的，我马上请门卫师傅来跟您说，请稍等一下别挂机。"

    # ---- tool 2: complete (validate, persist, push to guard) ----
    async def complete(self) -> str:
        missing = self.info.missing_labels_zh()
        if missing:
            return f"信息还不全，还差：{'、'.join(missing)}。请先补齐再调用完成登记。"

        self.info.stamp_entry_time(self.tz)
        payload = self.info.to_dict()
        payload["returning"] = bool(self.returning_match)
        if self.returning_match:
            payload["returning_summary"] = self._returning_summary(self.returning_match)
            payload["last_company"] = self.returning_match.get("last_company")
            payload["last_reason"] = self.returning_match.get("last_reason")
        if self.access_match:
            payload["access_status"] = self.access_match.get("status")
            payload["access_reason"] = self.access_match.get("reason")
            payload["access_summary"] = self._access_summary(self.access_match)
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

    def __init__(self, settings, room: str | None = None) -> None:
        self.s = settings
        self.room = room  # LiveKit room of the live call (for the approved ping)
        self.last_visit_id: int | None = None  # so a DTMF release can confirm it

    async def notify(self, info: dict) -> str:
        import secrets

        from .db import repo
        from .notify import dispatch, gate

        if self.room and not info.get("room"):
            info["room"] = self.room
        token = secrets.token_urlsafe(16)
        visit = repo.create_visit(info, confirm_token=token, status="pending")
        self.last_visit_id = visit.id
        confirm_url = f"{self.s.public_base_url.rstrip('/')}/confirm?token={token}"

        # Whitelist fast-track: if enabled, a pre-approved visitor is confirmed
        # and the gate opens immediately (no guard tap). Off by default — the
        # card still flags ✅常客 and the guard confirms. Blacklist never auto-passes.
        if (
            info.get("access_status") == "whitelist"
            and getattr(self.s, "auto_pass_whitelist", False)
        ):
            repo.mark_confirmed_by_id(visit.id)
            gate.open_gate(visit_id=visit.id, plate=visit.plate)
            cid = f"visit-{visit.id}"
            repo.log_event(cid, "confirmed", text=f"常客自动放行 {visit.plate or ''}")
            repo.log_event(cid, "gate", text="已发送抬杆指令 (常客自动)")

        await dispatch.push(self.s, info, confirm_url)
        return confirm_url


def make_db_lookup() -> LookupReturning:
    """Returning-visitor lookup backed by the DB (used in the live path)."""
    from .db import repo

    def _lookup(plate: str | None, phone: str | None) -> dict | None:
        return repo.recognize(plate=plate, phone=phone)

    return _lookup
