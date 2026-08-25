"""Telegram webhook: unverified requests never reach the pipeline (doc 05).

Contract with the Telegram API:
- The webhook URL carries a hard-to-guess secret path segment; requests whose
  X-Telegram-Bot-Api-Secret-Token header does not match our configured value
  are rejected with 401 BEFORE any parsing (defense in depth, both layers).
- Only the message fields we need are read; everything else is dropped.
- Member identity is the chat_id (household membership mapping lands in P4
  with DynamoDB; until then a local allowlist in settings-driven code).

The handler is transport-agnostic: FastAPI wiring happens in the deploy layer;
this module stays importable and testable without a server.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Any

from gatehouse.config import Settings


class WebhookError(Exception):
    """Raised for any request that must not be processed."""


@dataclass(frozen=True)
class InboundSignal:
    """The minimal, validated shape extracted from one Telegram update."""

    update_id: int
    chat_id: int
    sender_name: str
    text: str
    is_forward: bool


def verify_secret(header_value: str | None, settings: Settings) -> None:
    """Constant-time comparison; mismatch raises WebhookError."""
    expected = settings.telegram_webhook_secret
    if not expected:
        raise WebhookError("webhook secret not configured")
    if not header_value or not hmac.compare_digest(header_value, expected):
        raise WebhookError("bad webhook secret")


def parse_update(payload: dict[str, Any]) -> InboundSignal:
    """Extract the inbound signal from one Telegram update.

    Raises WebhookError for malformed, non-message, or empty-text updates so
    the caller can 400/422 without touching the pipeline.
    """
    update_id_raw = payload.get("update_id")
    if not isinstance(update_id_raw, int):
        raise WebhookError("missing update_id")

    message = payload.get("message")
    if not isinstance(message, dict):
        raise WebhookError("not a message update")

    chat = message.get("chat")
    chat_id = chat.get("id") if isinstance(chat, dict) else None
    if not isinstance(chat_id, int):
        raise WebhookError("missing chat id")

    from_user = message.get("from") or {}
    sender_name = str(from_user.get("first_name", "unknown"))[:40]

    text = message.get("text") or message.get("caption") or ""
    if not isinstance(text, str) or not text.strip():
        raise WebhookError("no text content")

    is_forward = "forward_origin" in message or "forward_from" in message

    return InboundSignal(
        update_id=update_id_raw,
        chat_id=chat_id,
        sender_name=sender_name,
        text=text[:4000],  # hard cap: bounded prompts, bounded spend
        is_forward=is_forward,
    )


def is_panic_request(text: str) -> bool:
    """True when a member explicitly fires the /panic keyword.

    Strict match on the command form only: the word 'panic' alone must never
    escalate anyone's evening.
    """
    return text.strip().lower().startswith("/panic")


def build_reply_verdict(package_verdict: str, reason_codes: list[str]) -> str:
    """Member-facing reply text. Guardian-facing cards come via the console.

    Tone contract (doc 05 section 6): short, calm, no jargon, no fear.
    """
    if package_verdict == "SCAM":
        return (
            "⚠️ This looks like a scam. Do not pay, click, or share OTPs.\n"
            "Your family guardian has been notified with the full evidence."
        )
    if package_verdict == "SUSPICIOUS":
        return (
            "🤔 We found some warning signs here and are checking deeper.\n"
            "Hold off on any payment until your guardian confirms."
        )
    return "✅ Nothing harmful found in this message."
