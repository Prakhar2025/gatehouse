"""Tests for the Telegram webhook contract."""

from __future__ import annotations

import pytest

from gatehouse.channels.telegram import (
    InboundSignal,
    WebhookError,
    build_reply_verdict,
    parse_update,
    verify_secret,
)
from gatehouse.config import Settings


@pytest.fixture()
def settings() -> Settings:
    return Settings(environment="local", telegram_webhook_secret="test-secret-123")  # noqa: S106


class TestSecretVerification:
    def test_missing_config_rejects(self) -> None:
        with pytest.raises(WebhookError, match="not configured"):
            verify_secret("anything", Settings(environment="local"))

    def test_wrong_secret_rejected(self, settings: Settings) -> None:
        with pytest.raises(WebhookError, match="bad webhook secret"):
            verify_secret("wrong", settings)

    def test_correct_secret_passes(self, settings: Settings) -> None:
        verify_secret("test-secret-123", settings)  # must not raise

    def test_none_header_rejected(self, settings: Settings) -> None:
        with pytest.raises(WebhookError):
            verify_secret(None, settings)


class TestParseUpdate:
    def _payload(self, **overrides: dict[str, object]) -> dict[str, object]:
        base = {
            "update_id": 1001,
            "message": {
                "chat": {"id": 5500012},
                "from": {"first_name": "Ravi"},
                "text": "check this kyc message",
            },
        }
        base.update(overrides)
        return base

    def test_happy_path(self) -> None:
        sig = parse_update(self._payload())
        assert isinstance(sig, InboundSignal)
        assert sig.chat_id == 5500012
        assert sig.sender_name == "Ravi"
        assert sig.is_forward is False

    def test_forward_detected(self) -> None:
        payload = self._payload()
        message = dict(payload["message"])  # type: ignore[call-overload]
        message["forward_origin"] = {}
        payload["message"] = message
        sig = parse_update(payload)
        assert sig.is_forward is True

    def test_caption_used_for_media(self) -> None:
        payload = self._payload()
        payload["message"] = {
            "chat": {"id": 1},
            "from": {"first_name": "A"},
            "photo": [{}],
            "caption": "look at this upi screenshot",
        }
        sig = parse_update(payload)
        assert "upi screenshot" in sig.text

    def test_missing_update_id_rejected(self) -> None:
        with pytest.raises(WebhookError, match="update_id"):
            parse_update({"message": {}})

    def test_non_message_update_rejected(self) -> None:
        with pytest.raises(WebhookError, match="not a message"):
            parse_update({"update_id": 5, "edited_message": {}})

    def test_empty_text_rejected(self) -> None:
        payload = self._payload()
        message = dict(payload["message"])  # type: ignore[call-overload]
        message["text"] = "   "
        payload["message"] = message
        with pytest.raises(WebhookError, match="no text"):
            parse_update(payload)

    def test_text_hard_capped(self) -> None:
        payload = self._payload()
        message = dict(payload["message"])  # type: ignore[call-overload]
        message["text"] = "x" * 99999
        payload["message"] = message
        sig = parse_update(payload)
        assert len(sig.text) == 4000


class TestReplyTone:
    def test_scam_reply_warns_without_panicking(self) -> None:
        reply = build_reply_verdict("SCAM", ["HARD_FAIL_ISSUER_RULE"])
        assert "scam" in reply.lower()
        assert "Do not pay" in reply

    def test_suspicious_reply_tells_to_hold(self) -> None:
        reply = build_reply_verdict("SUSPICIOUS", [])
        assert "Hold off" in reply

    def test_safe_reply_is_quiet(self) -> None:
        reply = build_reply_verdict("SAFE", [])
        assert "✅" in reply
