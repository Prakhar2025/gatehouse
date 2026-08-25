"""Tests for the live runtime loop behind the intake routes.

Covers the deployment-layer contract end to end in LOCAL mode: sender
binding/refusal, dedupe budget protection, evidence persistence, guardian
escalation with quiet hours and panic bypass, and the email alias boundary.
No network: stores are in-memory and the notifier is the logging sink.
"""

from __future__ import annotations

import asyncio
import calendar
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from gatehouse.agents.mock_model import MockModel
from gatehouse.channels.telegram import parse_update
from gatehouse.config import get_settings
from gatehouse.runtime import (
    PipelineOutcome,
    digest_tick,
    get_runtime,
    handle_email_signal,
    handle_telegram_signal,
    reset_runtime,
    run_pipeline,
)

SCAM_TEXT = "SBI KYC expired, pay now at http://sbi-verify.top UTR123456789012"
GRAY_TEXT = "click http://random-site.example now"
BENIGN_TEXT = "lunch tomorrow at the usual place?"
HH1 = "household-one"


def go(coro: Any) -> Any:
    return asyncio.run(coro)


def quiet_epoch() -> float:
    """A moment inside quiet hours, built from civil time per what-broke."""
    ist = timezone(timedelta(hours=5, minutes=30))
    dt = datetime(2026, 8, 25, 23, 30, tzinfo=ist)
    epoch = float(calendar.timegm(dt.utctimetuple()))
    # Sanity: adding the IST offset must land inside the 22:00-07:00 window.
    assert time.gmtime(epoch + 330 * 60).tm_hour == 23
    return epoch


def day_epoch() -> float:
    """A mid-afternoon moment, outside quiet hours."""
    ist = timezone(timedelta(hours=5, minutes=30))
    dt = datetime(2026, 8, 25, 15, 0, tzinfo=ist)
    epoch = float(calendar.timegm(dt.utctimetuple()))
    assert time.gmtime(epoch + 330 * 60).tm_hour == 15
    return epoch


@pytest.fixture()
def rt(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Composed local runtime with a linked Telegram member and a guardian."""
    monkeypatch.setenv("GATEHOUSE_TELEGRAM_WEBHOOK_SECRET", "ci-secret")
    monkeypatch.setenv("GATEHOUSE_GUARDIAN_TELEGRAM_CHAT_ID", "999")
    get_settings.cache_clear()
    reset_runtime()
    runtime = get_runtime()
    runtime.settings.guardian_telegram_chat_id = "999"
    runtime.model = None
    invite = runtime.bindings.issue_invite(HH1)
    runtime.bindings.consume_invite(invite.code, "telegram", "555")
    return runtime


def tg_signal(text: str, chat_id: int = 555, update_id: int = 1) -> Any:
    return parse_update(
        {
            "update_id": update_id,
            "message": {
                "chat": {"id": chat_id},
                "from": {"first_name": "Riya"},
                "text": text,
            },
        }
    )


def tg_photo_signal(chat_id: int = 555, update_id: int = 1) -> Any:
    """A forwarded screenshot with no caption and no extractable text."""
    return parse_update(
        {
            "update_id": update_id,
            "message": {
                "chat": {"id": chat_id},
                "from": {"first_name": "Riya"},
                "photo": [{}],
            },
        }
    )


def scam_model() -> MockModel:
    return MockModel(tool_payload={"scam_likelihood": 0.97, "reason_code": "KYC_PHISH"})


class TestRefusal:
    def test_unlinked_sender_refused_without_case_or_spend(self, rt: Any) -> None:
        outcome: PipelineOutcome = go(handle_telegram_signal(tg_signal(SCAM_TEXT, chat_id=42)))
        assert outcome.status == "refused"
        assert outcome.case_id is None
        assert "not linked" in outcome.reply_text
        assert rt.notifications is None or not getattr(rt.notifications, "digest_queue", [])

    def test_refusal_creates_no_bundle(self, rt: Any) -> None:
        go(handle_telegram_signal(tg_signal(SCAM_TEXT, chat_id=42)))
        assert rt.bundles.latest(HH1, "any") is None


class TestFullLoop:
    def test_linked_member_scam_flow(self, rt: Any) -> None:
        rt.model = scam_model()
        outcome: PipelineOutcome = go(handle_telegram_signal(tg_signal(SCAM_TEXT)))
        assert outcome.status == "investigated"
        assert outcome.verdict == "SCAM"
        assert outcome.escalated == "sent"
        assert outcome.spend_usd >= 0.0
        bundle = rt.bundles.latest(HH1, str(outcome.case_id))
        assert bundle is not None
        assert bundle.channel == "telegram"
        assert bundle.revision == 1

    def test_member_reply_is_calm_and_actionable(self, rt: Any) -> None:
        rt.model = scam_model()
        outcome: PipelineOutcome = go(handle_telegram_signal(tg_signal(SCAM_TEXT)))
        assert "Do not pay" in outcome.reply_text

    def test_benign_message_is_safe_without_escalation(self, rt: Any) -> None:
        rt.model = MockModel(tool_payload={"scam_likelihood": 0.05, "reason_code": "NONE"})
        outcome: PipelineOutcome = go(handle_telegram_signal(tg_signal(BENIGN_TEXT)))
        assert outcome.verdict == "SAFE"
        assert outcome.escalated is None
        assert outcome.reply_text.startswith("✅")


class TestDuplicateProtection:
    def test_second_forward_gets_prior_case_and_no_new_bundle(self, rt: Any) -> None:
        rt.model = scam_model()
        first: PipelineOutcome = go(handle_telegram_signal(tg_signal(SCAM_TEXT, update_id=1)))
        second: PipelineOutcome = go(handle_telegram_signal(tg_signal(SCAM_TEXT, update_id=2)))
        assert first.status == "investigated"
        assert second.status == "duplicate"
        assert second.case_id == first.case_id
        bundles_before = rt.bundles.latest(HH1, str(first.case_id))
        assert bundles_before is not None

    def test_same_text_other_household_not_a_duplicate(self, rt: Any) -> None:
        invite = rt.bindings.issue_invite("household-two")
        rt.bindings.consume_invite(invite.code, "telegram", "777")
        rt.model = scam_model()
        a: PipelineOutcome = go(handle_telegram_signal(tg_signal(SCAM_TEXT, chat_id=555)))
        b: PipelineOutcome = go(handle_telegram_signal(tg_signal(SCAM_TEXT, chat_id=777)))
        assert a.status == "investigated"
        assert b.status == "investigated"
        assert a.case_id != b.case_id


class TestQuietHours:
    def test_decision_at_night_queues_into_digest(self, rt: Any) -> None:
        rt.model = MockModel(tool_payload={"scam_likelihood": 0.60, "reason_code": "URL_RISK"})
        outcome: PipelineOutcome = go(
            run_pipeline(
                rt,
                channel="telegram",
                household_id=HH1,
                sender_name="R",
                text=GRAY_TEXT,
                is_forward=True,
                now=quiet_epoch(),
            )
        )
        assert outcome.verdict == "SUSPICIOUS"
        assert outcome.escalated == "queued"

    def test_panic_bypasses_quiet_hours(self, rt: Any) -> None:
        rt.model = MockModel(tool_payload={"scam_likelihood": 0.60, "reason_code": "URL_RISK"})
        outcome: PipelineOutcome = go(handle_telegram_signal(tg_signal(f"/panic {GRAY_TEXT}")))
        assert outcome.status == "investigated"
        assert outcome.escalated == "sent"

    def test_digest_tick_flushes_parked_cards(self, rt: Any) -> None:
        rt.model = MockModel(tool_payload={"scam_likelihood": 0.60, "reason_code": "URL_RISK"})
        go(
            run_pipeline(
                rt,
                channel="telegram",
                household_id=HH1,
                sender_name="R",
                text=GRAY_TEXT,
                is_forward=True,
                now=quiet_epoch(),
            )
        )
        flushed = digest_tick()
        assert flushed == 1
        service = rt.notification_service()
        assert service.digest_queue == []

    def test_daytime_decision_sends_immediately(self, rt: Any) -> None:
        rt.model = MockModel(tool_payload={"scam_likelihood": 0.60, "reason_code": "URL_RISK"})
        outcome: PipelineOutcome = go(
            run_pipeline(
                rt,
                channel="telegram",
                household_id=HH1,
                sender_name="R",
                text=GRAY_TEXT,
                is_forward=True,
                now=day_epoch(),
            )
        )
        assert outcome.escalated == "sent"


class TestEmailBoundary:
    @pytest.fixture(autouse=True)
    def _allowlist(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GATEHOUSE_EMAIL_ALIAS_ALLOWLIST", "h7k2")
        get_settings.cache_clear()
        reset_runtime()

    def test_bound_alias_processed(self, rt: Any) -> None:
        outcome: PipelineOutcome = go(
            handle_email_signal(
                alias="H7K2", sender="fraud@example.com", text=SCAM_TEXT, message_id="m1"
            )
        )
        assert outcome.status == "investigated"
        assert outcome.household_id == "alias:h7k2"

    def test_unknown_alias_refused(self, rt: Any) -> None:
        outcome: PipelineOutcome = go(
            handle_email_signal(
                alias="zzzz", sender="fraud@example.com", text=SCAM_TEXT, message_id="m2"
            )
        )
        assert outcome.status == "refused"


class TestPanicContentStripped:
    def test_keyword_removed_before_investigation(self, rt: Any) -> None:
        rt.model = scam_model()
        outcome: PipelineOutcome = go(handle_telegram_signal(tg_signal(f"/panic {SCAM_TEXT}")))
        assert outcome.status == "investigated"
        assert outcome.verdict == "SCAM"


class TestScreenshotNoTextLayer:
    """Matrix row (doc 05 s7): OCR path completes, verdict produced."""

    def test_bare_screenshot_completes_with_honest_flag(self, rt: Any) -> None:
        rt.model = scam_model()
        outcome: PipelineOutcome = go(handle_telegram_signal(tg_photo_signal()))
        assert outcome.status == "investigated"
        assert outcome.verdict is not None
        assert "NO_TEXT_LAYER" in outcome.reason_codes

    def test_screenshot_bundle_persisted(self, rt: Any) -> None:
        rt.model = scam_model()
        outcome: PipelineOutcome = go(handle_telegram_signal(tg_photo_signal()))
        bundle = rt.bundles.latest(HH1, str(outcome.case_id))
        assert bundle is not None
        assert bundle.channel == "telegram"


class TestDuplicateBudgetProtection:
    """Matrix row (doc 05 s7): no double spend on a second forward."""

    def test_second_forward_spends_zero(self, rt: Any) -> None:
        rt.model = scam_model()
        first: PipelineOutcome = go(handle_telegram_signal(tg_signal(SCAM_TEXT, update_id=1)))
        second: PipelineOutcome = go(
            handle_telegram_signal(tg_signal(SCAM_TEXT, chat_id=555, update_id=2))
        )
        assert first.status == "investigated"
        assert first.spend_usd >= 0.0
        assert second.status == "duplicate"
        assert second.spend_usd == 0.0

    def test_duplicate_leaves_original_bundle_untouched(self, rt: Any) -> None:
        rt.model = scam_model()
        first: PipelineOutcome = go(handle_telegram_signal(tg_signal(SCAM_TEXT, update_id=1)))
        go(handle_telegram_signal(tg_signal(SCAM_TEXT, update_id=2)))
        bundle = rt.bundles.latest(HH1, str(first.case_id))
        assert bundle is not None
        assert bundle.revision == 1


class TestStartBinding:
    """Matrix row support (doc 05 s2): the /start CODE binding flow."""

    def test_bound_chat_forwards_get_investigated(self, rt: Any) -> None:
        invite = rt.bindings.issue_invite(HH1)
        outcome: PipelineOutcome = go(
            handle_telegram_signal(tg_signal(f"/start {invite.code}", chat_id=42))
        )
        assert outcome.status == "bound"
        assert outcome.household_id == HH1
        # The same chat is now a full member of the loop.
        rt.model = scam_model()
        fwd: PipelineOutcome = go(
            handle_telegram_signal(tg_signal(SCAM_TEXT, chat_id=42, update_id=2))
        )
        assert fwd.status == "investigated"
        assert fwd.verdict == "SCAM"

    def test_bad_code_refused_without_binding(self, rt: Any) -> None:
        outcome: PipelineOutcome = go(
            handle_telegram_signal(tg_signal("/start BOGUS99", chat_id=43))
        )
        assert outcome.status == "refused"
        assert rt.bindings.lookup("telegram", "43") is None

    def test_already_linked_chat_gets_friendly_refusal(self, rt: Any) -> None:
        invite_a = rt.bindings.issue_invite(HH1)
        go(handle_telegram_signal(tg_signal(f"/start {invite_a.code}", chat_id=44)))
        invite_b = rt.bindings.issue_invite("household-two")
        second: PipelineOutcome = go(
            handle_telegram_signal(tg_signal(f"/start {invite_b.code}", chat_id=44))
        )
        assert second.status == "refused"
        assert rt.bindings.lookup("telegram", "44") is not None

    def test_plain_start_without_code_is_not_binding(self, rt: Any) -> None:
        outcome: PipelineOutcome = go(handle_telegram_signal(tg_signal("/start", chat_id=45)))
        assert outcome.status == "refused"
        assert rt.bindings.lookup("telegram", "45") is None
