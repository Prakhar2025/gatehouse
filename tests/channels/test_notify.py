"""Tests for the notification service: quiet hours, emergency bypass, digest."""

from __future__ import annotations

import time
from calendar import timegm
from datetime import UTC, datetime
from typing import Any

import pytest

from gatehouse.channels.notify import (
    EMERGENCY_FOLLOWUP_SECONDS,
    EscalationCard,
    LoggingNotifier,
    NotificationError,
    NotificationService,
    QuietHoursPolicy,
    _format_card,
)
from gatehouse.config import Settings


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {"guardian_telegram_chat_id": "guardian-1"}
    base.update(overrides)
    return Settings(environment="local", **base)


def _card(urgency: str = "DECISION", case_id: str = "case-1") -> EscalationCard:
    return EscalationCard(
        household_id="fam-1",
        case_id=case_id,
        urgency=urgency,
        title="Fake bank KYC demand",
        summary="UPI demand with urgency markers; 3 rule hits.",
    )


# Fixtures built from civil time, never hand-computed epochs.
def _utc_ts(hour: int, minute: int = 0) -> float:
    return float(timegm(datetime(2026, 8, 25, hour, minute, tzinfo=UTC).timetuple()))


_QUIET_TS = _utc_ts(23, 30)  # 23:30 UTC == 05:00 IST next day (inside 22-07)
_AWAKE_TS = _utc_ts(16, 0)  # 16:00 UTC == 21:30 IST (outside)
assert time.gmtime(_QUIET_TS).tm_hour == 23
assert time.gmtime(_AWAKE_TS + 330 * 60).tm_hour == 21


class TestQuietHoursPolicy:
    def test_default_window_covers_night(self) -> None:
        policy = QuietHoursPolicy()
        s = _settings()
        assert policy.is_quiet(_QUIET_TS, s)
        assert not policy.is_quiet(_AWAKE_TS, s)

    def test_disabled_policy_never_quiet(self) -> None:
        policy = QuietHoursPolicy()
        assert not policy.is_quiet(_QUIET_TS, _settings(quiet_hours_enabled=False))

    def test_invalid_window_refused(self) -> None:
        with pytest.raises(ValueError):
            QuietHoursPolicy(start_hour=7, end_hour=7)


class TestEscalationRouting:
    def test_decision_outside_hours_sends(self) -> None:
        notifier = LoggingNotifier()
        svc = NotificationService(notifier)
        outcome = svc.escalate(_card(), _settings(), now=_AWAKE_TS)
        assert outcome == "sent"
        assert len(notifier.sent) == 1

    def test_decision_in_quiet_hours_queues(self) -> None:
        notifier = LoggingNotifier()
        svc = NotificationService(notifier)
        outcome = svc.escalate(_card(), _settings(), now=_QUIET_TS)
        assert outcome == "queued"
        assert notifier.sent == []

    def test_emergency_bypasses_quiet_hours(self) -> None:
        notifier = LoggingNotifier()
        svc = NotificationService(notifier)
        outcome = svc.escalate(_card(urgency="EMERGENCY"), _settings(), now=_QUIET_TS)
        assert outcome == "sent"
        assert len(notifier.sent) == 1

    def test_unknown_urgency_raises(self) -> None:
        svc = NotificationService(LoggingNotifier())
        with pytest.raises(NotificationError):
            svc.escalate(_card(urgency="WHISPER"), _settings())

    def test_missing_guardian_chat_raises(self) -> None:
        svc = NotificationService(LoggingNotifier())
        # Awake-hour timestamp: a default wall-clock read can land inside
        # quiet hours, where the card queues before the guard ever fires.
        with pytest.raises(NotificationError):
            svc.escalate(_card(), _settings(guardian_telegram_chat_id=""), now=_AWAKE_TS)


class TestDigestFallback:
    def test_failed_send_parks_for_digest(self) -> None:
        class Failing:
            def send(self, chat_id: str, text: str) -> bool:
                return False

        svc = NotificationService(Failing())
        outcome = svc.escalate(_card(), _settings(), now=_AWAKE_TS)
        assert outcome == "queued"

    def test_emergency_send_failure_is_loud(self) -> None:
        class Failing:
            def send(self, chat_id: str, text: str) -> bool:
                return False

        svc = NotificationService(Failing())
        with pytest.raises(NotificationError):
            svc.escalate(_card(urgency="EMERGENCY"), _settings(), now=_AWAKE_TS)

    def test_flush_digest_delivers_and_clears(self) -> None:
        notifier = LoggingNotifier()
        svc = NotificationService(notifier)
        svc.escalate(_card(case_id="c1"), _settings(), now=_QUIET_TS)
        svc.escalate(_card(case_id="c2"), _settings(), now=_QUIET_TS)
        assert notifier.sent == []
        delivered = svc.flush_digest(_settings())
        assert delivered == 2
        assert len(notifier.sent) == 1
        text = notifier.sent[0]["text"]
        assert "Case c1" in text and "Case c2" in text

    def test_flush_empty_returns_zero(self) -> None:
        assert NotificationService(LoggingNotifier()).flush_digest(_settings()) == 0


class TestEmergencyFollowup:
    def test_followup_due_after_ten_minutes(self) -> None:
        svc = NotificationService(LoggingNotifier())
        svc.escalate(_card(urgency="EMERGENCY"), _settings(), now=_AWAKE_TS)
        assert svc.due_followups(now=_AWAKE_TS + EMERGENCY_FOLLOWUP_SECONDS - 1) == []
        assert svc.due_followups(now=_AWAKE_TS + EMERGENCY_FOLLOWUP_SECONDS + 1) == ["case-1"]

    def test_due_cases_not_repeated(self) -> None:
        svc = NotificationService(LoggingNotifier())
        svc.escalate(_card(urgency="EMERGENCY"), _settings(), now=_AWAKE_TS)
        assert svc.due_followups(now=_AWAKE_TS + EMERGENCY_FOLLOWUP_SECONDS + 5) == ["case-1"]
        assert svc.due_followups(now=_AWAKE_TS + EMERGENCY_FOLLOWUP_SECONDS + 6) == []


class TestCardFormat:
    def test_emergency_marker(self) -> None:
        text = _format_card(_card(urgency="EMERGENCY"))
        assert text.startswith("URGENT") and "Case case-1" in text

    def test_decision_marker(self) -> None:
        text = _format_card(_card())
        assert text.startswith("REVIEW")
