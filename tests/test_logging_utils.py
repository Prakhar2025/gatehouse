"""Scrubber tests: the CI canary guarantee that P1 never reaches logs.

These tests double as the enforcement mechanism promised in docs/18 section 9:
seeded sentinel strings MUST come out redacted from any formatted record.
"""

from __future__ import annotations

import json
import logging

from gatehouse.constants import REDACTION_TOKEN
from gatehouse.logging_utils import ScrubbedJsonFormatter, configure_logging, get_logger, scrub_p1

SENTINEL_PHONE = "+91 98765 43210"
SENTINEL_EMAIL = "victim.name@gmail.com"
SENTINEL_VPA = "scammerpay@ybl"
SENTINEL_CARD = "4111 1111 1111 1111"


def test_phone_redacted() -> None:
    out = scrub_p1(f"call came from {SENTINEL_PHONE} today")
    assert SENTINEL_PHONE not in out
    assert REDACTION_TOKEN in out


def test_email_redacted() -> None:
    out = scrub_p1(f"reply to {SENTINEL_EMAIL} now")
    assert SENTINEL_EMAIL not in out


def test_vpa_redacted() -> None:
    out = scrub_p1(f"send money to {SENTINEL_VPA} urgently")
    assert SENTINEL_VPA not in out


def test_cardish_redacted() -> None:
    out = scrub_p1(f"card {SENTINEL_CARD} ends valid")
    assert "4111" not in out


def test_safe_text_untouched() -> None:
    text = "Your KYC has expired, click http://evil.example now or account blocked"
    assert scrub_p1(text) == text


def test_formatted_record_contains_no_p1() -> None:
    """The end-to-end canary: nothing P1-shaped survives formatting."""
    configure_logging()
    logger = get_logger("gatehouse.test.canary")
    formatter = ScrubbedJsonFormatter()
    record = logger.makeRecord(
        name="gatehouse.test.canary",
        level=logging.INFO,
        fn="test",
        lno=1,
        msg="forwarded message from %s about %s",
        args=(SENTINEL_PHONE, SENTINEL_VPA),
        exc_info=None,
    )
    raw = formatter.format(record)
    payload = json.loads(raw)
    for secret in (SENTINEL_PHONE, SENTINEL_EMAIL, SENTINEL_VPA, SENTINEL_CARD):
        assert secret not in raw
    assert "msg" in payload and "ts" in payload and "level" in payload


def test_extra_context_scrubbed_recursively() -> None:
    formatter = ScrubbedJsonFormatter()
    logger = logging.getLogger("gatehouse.test.extra")
    record = logger.makeRecord(
        name="gatehouse.test.extra",
        level=logging.INFO,
        fn="t",
        lno=1,
        msg="case processed",
        args=(),
        exc_info=None,
    )
    record.gh_extra = {"member_contact": {"phone": SENTINEL_PHONE}, "ids": [SENTINEL_VPA]}
    raw = formatter.format(record)
    assert SENTINEL_PHONE not in raw
    assert SENTINEL_VPA not in raw
