"""SES email intake: per-household alias, receipt-rule Lambda contract (doc 05 section 4).

Each household gets a hashed inbound alias (h7k2@gatehouse.in). SES receives,
applies spam/virus verdicts, and invokes this module's shape via a receipt
rule; the Lambda event carries the full MIME message base64-encoded.

Contract:
- SES built-in trust: the invocation itself is the auth boundary (no public
  URL exists), so there is no signature header to verify. We still validate
  structure and refuse anything malformed before parsing.
- Alias -> household mapping is a settings-driven allowlist in v1 (same
  discipline as Telegram chat allowlists); DynamoDB mapping lands in P4.
- Text extraction is plain-text part first, HTML stripped as fallback. Bounded
  at the same 4000-char cap as every channel.
"""

from __future__ import annotations

import base64
import email.policy
import re
from dataclasses import dataclass
from email.parser import BytesParser
from typing import Any

TEXT_CAP = 4000

_ALIAS_RE = re.compile(r"^[a-z0-9]{4,32}$")


class EmailIntakeError(Exception):
    """Raised for any email delivery that must not reach the pipeline."""


@dataclass(frozen=True)
class EmailSignal:
    """Minimal validated shape from one SES receipt-rule Lambda event."""

    message_id: str
    recipient_alias: str
    sender: str
    subject: str
    text: str


def parse_receipt_event(event: dict[str, Any]) -> EmailSignal:
    """Extract one email signal from an SES receipt-rule Lambda invocation.

    Raises EmailIntakeError on malformed events, missing content, or a
    recipient alias that fails basic hygiene (never leaks into logs).
    """
    records = event.get("Records")
    if not isinstance(records, list) or not records:
        raise EmailIntakeError("not an ses event")

    record = records[0]
    if str(record.get("eventSource", "")) != "aws:ses":
        raise EmailIntakeError("unexpected event source")

    ses = record.get("ses") or {}
    receipt = ses.get("receipt") or {}
    # Refuse deliveries SES already flagged; verdicts arrive before we spend.
    if str(receipt.get("spamVerdict", {}).get("status", "")) == "FAIL":
        raise EmailIntakeError("ses marked spam")
    if str(receipt.get("virusVerdict", {}).get("status", "")) == "FAIL":
        raise EmailIntakeError("ses marked virus")

    mail = ses.get("mail") or {}
    destinations = mail.get("destination") or []
    recipients = [d for d in destinations if isinstance(d, str)]
    if not recipients:
        raise EmailIntakeError("missing destination")

    alias = recipients[0].split("@")[0].lower()
    if not _ALIAS_RE.match(alias):
        raise EmailIntakeError("bad alias shape")

    content = (mail.get("commonHeaders") or {}).get("subject") or ""
    body_text = ""
    raw_b64 = (mail.get("content") or "") or None
    if raw_b64:
        msg = BytesParser(policy=email.policy.default).parsebytes(base64.b64decode(raw_b64))
        body_text = _extract_body(msg)

    text = _compose_text(str(content), body_text)
    if not text.strip():
        raise EmailIntakeError("no usable content")

    return EmailSignal(
        message_id=str(mail.get("messageId", "")),
        recipient_alias=alias,
        sender=str(mail.get("source") or "unknown")[:120],
        subject=str(content)[:200],
        text=text[:TEXT_CAP],
    )


def _extract_body(msg: Any) -> str:
    """Prefer a non-empty plain-text part; fall back to tag-stripped HTML."""
    if msg.is_multipart():
        plain = msg.get_body(preferencelist=("plain",))
        if plain is not None:
            plain_text = str(plain.get_content()).strip()
            if plain_text:
                return plain_text
        html = msg.get_body(preferencelist=("html",))
        if html is not None:
            return _strip_html(str(html.get_content()))
        return ""
    payload = msg.get_content()
    if msg.get_content_type() == "text/html":
        return _strip_html(str(payload))
    return str(payload)


def _strip_html(html: str) -> str:
    """Drop script/style blocks entirely, then all tags, then collapse space."""
    without_blocks = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    without_tags = re.sub(r"<[^>]+>", " ", without_blocks)
    return re.sub(r"\s+", " ", without_tags).strip()


def _compose_text(subject: str, body: str) -> str:
    """Subject + body as one bounded working copy."""
    subject_line = f"Subject: {subject.strip()}" if subject.strip() else ""
    return "\n".join(part for part in (subject_line, body.strip()) if part)
