"""Tests for SES email intake: verdicts, alias hygiene, MIME extraction."""

from __future__ import annotations

import base64
from email.message import EmailMessage
from typing import Any

import pytest

from gatehouse.channels.email import EmailIntakeError, parse_receipt_event


def _mime_body(plain: str, html: str | None = None) -> str:
    msg = EmailMessage()
    msg["Subject"] = "KYC renewal"
    msg["From"] = "fraud@example.com"
    msg["To"] = "h7k2@gatehouse.in"
    msg.set_content(plain)
    if html is not None:
        msg.add_alternative(html, subtype="html")
    return base64.b64encode(msg.as_bytes()).decode()


def _event(**overrides: Any) -> dict[str, Any]:
    event: dict[str, Any] = {
        "Records": [
            {
                "eventSource": "aws:ses",
                "ses": {
                    "receipt": {
                        "spamVerdict": {"status": "PASS"},
                        "virusVerdict": {"status": "PASS"},
                    },
                    "mail": {
                        "messageId": "mid-1",
                        "source": "fraud@example.com",
                        "destination": ["H7K2@gatehouse.in"],
                        "commonHeaders": {"subject": "KYC renewal"},
                        "content": _mime_body("Your KYC expired. Pay 499 now."),
                    },
                },
            }
        ]
    }
    ses = event["Records"][0]["ses"]
    for path, value in overrides.items():
        part, key = path.split(".", 1)
        ses[part][key] = value
    return event


class TestReceiptParsing:
    def test_basic_extraction(self) -> None:
        s = parse_receipt_event(_event())
        assert s.recipient_alias == "h7k2"
        assert s.subject == "KYC renewal"
        assert s.message_id == "mid-1"
        assert "Subject: KYC renewal" in s.text
        assert "Pay 499" in s.text

    def test_html_fallback_stripped(self) -> None:
        event = _event(
            **{
                "mail.content": _mime_body(
                    "",
                    "<html><body>KYC <b>expired</b>.<script>evil()</script> Pay now</body></html>",
                )
            }
        )
        text = parse_receipt_event(event).text
        assert "expired" in text and "Pay now" in text
        assert "<b>" not in text and "evil()" not in text

    def test_text_cap(self) -> None:
        event = _event(**{"mail.content": _mime_body("x" * 9000)})
        assert len(parse_receipt_event(event).text) <= 4000


class TestRefusals:
    def test_spam_fail_refused(self) -> None:
        with pytest.raises(EmailIntakeError):
            parse_receipt_event(_event(**{"receipt.spamVerdict": {"status": "FAIL"}}))

    def test_virus_fail_refused(self) -> None:
        with pytest.raises(EmailIntakeError):
            parse_receipt_event(_event(**{"receipt.virusVerdict": {"status": "FAIL"}}))

    def test_wrong_source_refused(self) -> None:
        bad = _event()
        bad["Records"][0]["eventSource"] = "aws:s3"
        with pytest.raises(EmailIntakeError):
            parse_receipt_event(bad)

    def test_bad_alias_shape_refused(self) -> None:
        with pytest.raises(EmailIntakeError):
            parse_receipt_event(_event(**{"mail.destination": ["We!rd<>@gatehouse.in"]}))

    def test_empty_content_refused(self) -> None:
        with pytest.raises(EmailIntakeError):
            parse_receipt_event(
                _event(
                    **{
                        "mail.content": "",
                        "mail.commonHeaders": {"subject": ""},
                    }
                )
            )

    def test_missing_destination_refused(self) -> None:
        with pytest.raises(EmailIntakeError):
            parse_receipt_event(_event(**{"mail.destination": []}))
