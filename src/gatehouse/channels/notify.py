"""Notification service: guardian-facing delivery with quiet hours (doc 05 section 6).

The contract:
- DECISION escalations: single card, 1 retry then digest fallback.
- EMERGENCY (/panic or detected): card + follow-up ping after 10 minutes
  unactioned; the ONLY path allowed to bypass quiet hours (guardian consented
  at signup).
- Quiet hours default ON, 22:00 to 07:00 local: non-emergency escalations
  queue into the next morning digest instead of firing.

Delivery backends behind one Protocol: a logging sink for tests/dev and a
Telegram sender for prod. The Telegram sender is transport-only: it formats
nothing member-visible here beyond the guardian card itself.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol

from gatehouse.config import Settings

EMERGENCY_FOLLOWUP_SECONDS = 10 * 60


class NotificationError(Exception):
    """Raised when a notification cannot be accepted for delivery."""


class Notifier(Protocol):
    def send(self, chat_id: str, text: str) -> bool: ...


class LoggingNotifier:
    """Test/dev sink: records every send for assertion, delivers nothing."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def send(self, chat_id: str, text: str) -> bool:
        self.sent.append({"chat_id": chat_id, "text": text})
        return True


@dataclass(frozen=True)
class EscalationCard:
    """One guardian-facing escalation."""

    household_id: str
    case_id: str
    urgency: str  # DECISION or EMERGENCY
    title: str
    summary: str


@dataclass
class QueuedDigestItem:
    """An escalation parked by quiet hours, delivered in the morning digest."""

    card: EscalationCard
    queued_at: float


class QuietHoursPolicy:
    """22:00 to 07:00 local by default. Emergency bypass is explicit."""

    def __init__(self, start_hour: int = 22, end_hour: int = 7) -> None:
        if not (0 <= start_hour < 24 and 0 <= end_hour < 24 and start_hour != end_hour):
            raise ValueError("quiet hours window must be a valid hour range")
        self.start_hour = start_hour
        self.end_hour = end_hour

    def is_quiet(self, epoch_s: float, settings: Settings) -> bool:
        """Quiet iff quiet hours enabled AND local hour inside the window."""
        if not settings.quiet_hours_enabled:
            return False
        local_s = epoch_s + settings.quiet_hours_utc_offset_minutes * 60
        hour = time.gmtime(local_s).tm_hour
        if self.start_hour > self.end_hour:
            return hour >= self.start_hour or hour < self.end_hour
        return self.start_hour <= hour < self.end_hour


class NotificationService:
    """Accepts escalation cards, enforces quiet hours and retry/digest rules.

    The single-retry-then-digest rule from doc 05 is expressed through the
    notifier's return value: a False send parks the card for digest fallback
    instead of retrying inline (Lambda lifetime makes inline retries fragile;
    the digest path is the durable fallback).
    """

    def __init__(self, notifier: Notifier) -> None:
        self._notifier = notifier
        self.policy = QuietHoursPolicy()
        self.digest_queue: list[QueuedDigestItem] = []
        # case_id -> follow-up deadline (epoch seconds); EMERGENCY only.
        self.pending_followups: dict[str, float] = {}

    def escalate(self, card: EscalationCard, settings: Settings, now: float | None = None) -> str:
        """Route one escalation. Returns the outcome: sent | queued."""
        if card.urgency not in ("DECISION", "EMERGENCY"):
            raise NotificationError(f"unknown urgency: {card.urgency}")

        now_f = now if now is not None else time.time()
        emergency = card.urgency == "EMERGENCY"
        if not emergency and self.policy.is_quiet(now_f, settings):
            self.digest_queue.append(QueuedDigestItem(card=card, queued_at=now_f))
            return "queued"

        chat_id = settings.guardian_telegram_chat_id
        if not chat_id:
            raise NotificationError("no guardian chat configured")

        ok = self._notifier.send(chat_id, _format_card(card))
        if not ok:
            if emergency:
                raise NotificationError("emergency send failed")
            # One send attempt failed; digest fallback per doc 05 section 6.
            self.digest_queue.append(QueuedDigestItem(card=card, queued_at=now_f))
            return "queued"

        if emergency:
            self.pending_followups[card.case_id] = now_f + EMERGENCY_FOLLOWUP_SECONDS
        return "sent"

    def flush_digest(self, settings: Settings) -> int:
        """Send everything parked during quiet hours as one morning digest."""
        if not self.digest_queue:
            return 0
        lines = ["Overnight summary:", ""]
        for item in self.digest_queue:
            lines.append(_format_card(item.card))
            lines.append("")
        chat_id = settings.guardian_telegram_chat_id
        if not chat_id:
            raise NotificationError("no guardian chat configured")
        self._notifier.send(chat_id, "\n".join(lines).strip())
        count = len(self.digest_queue)
        self.digest_queue.clear()
        return count

    def due_followups(self, now: float | None = None) -> list[str]:
        """EMERGENCY cards unactioned past 10 minutes; caller pings the guardian."""
        now_f = now if now is not None else time.time()
        due = [case_id for case_id, at in self.pending_followups.items() if at <= now_f]
        for case_id in due:
            del self.pending_followups[case_id]
        return due


def _format_card(card: EscalationCard) -> str:
    """Guardian card format. Calm, short, evidence-first (doc 05 section 6)."""
    marker = "URGENT" if card.urgency == "EMERGENCY" else "REVIEW"
    header = f"{marker} {card.title} ({card.urgency})"
    return f"{header}\n{card.summary}\nCase {card.case_id}"
