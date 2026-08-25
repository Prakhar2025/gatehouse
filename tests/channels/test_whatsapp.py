"""Tests for the WhatsApp webhook skeleton: signatures, parsing, flag gate."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import pytest

from gatehouse.channels.whatsapp import (
    WhatsAppWebhookError,
    build_reply,
    parse_verification,
    parse_webhook,
    verify_signature,
    verify_subscription_token,
)
from gatehouse.config import Settings


def _settings(**overrides: Any) -> Settings:
    base = {
        "whatsapp_enabled": True,
        "whatsapp_verify_token": "vt-token",
        "whatsapp_app_secret": "app-secret",
    }
    base.update(overrides)
    return Settings(environment="local", **base)  # type: ignore[arg-type]


def _payload() -> dict[str, Any]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"display_phone_number": "15550001111"},
                            "contacts": [{"profile": {"name": "Riya"}}],
                            "messages": [
                                {
                                    "id": "wamid.1",
                                    "from": "919000000000",
                                    "type": "text",
                                    "text": {"body": "win prize click link"},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ]
            }
        ],
    }


def _sig(body: bytes, key: str = "app-secret") -> str:
    return "sha256=" + hmac.new(key.encode(), body, hashlib.sha256).hexdigest()


class TestSignature:
    def test_valid_signature_passes(self) -> None:
        body = b'{"object":"whatsapp_business_account"}'
        verify_signature(_sig(body), body, _settings())

    def test_tampered_body_fails(self) -> None:
        with pytest.raises(WhatsAppWebhookError):
            verify_signature(_sig(b"a"), b"b", _settings())

    def test_missing_header_fails(self) -> None:
        with pytest.raises(WhatsAppWebhookError):
            verify_signature(None, b"{}", _settings())

    def test_wrong_secret_fails(self) -> None:
        body = b"{}"
        with pytest.raises(WhatsAppWebhookError):
            verify_signature(_sig(body, "other"), body, _settings())

    def test_unconfigured_secret_fails_closed(self) -> None:
        with pytest.raises(WhatsAppWebhookError):
            verify_signature(_sig(b"{}"), b"{}", _settings(whatsapp_app_secret=""))


class TestParse:
    def test_text_message_extracted(self) -> None:
        signals = parse_webhook(_payload())
        assert len(signals) == 1
        s = signals[0]
        assert s.text == "win prize click link"
        assert s.sender_name == "Riya"
        assert s.message_id == "wamid.1"
        assert not s.has_media

    def test_image_with_caption_counts_media(self) -> None:
        p = _payload()
        p["entry"][0]["changes"][0]["value"]["messages"][0] = {
            "id": "wamid.2",
            "from": "919000000000",
            "type": "image",
            "image": {"caption": "payment proof", "mime_type": "image/jpeg"},
        }
        (s,) = parse_webhook(p)
        assert s.has_media and s.media_mime == "image/jpeg" and s.text == "payment proof"

    def test_document_with_mime(self) -> None:
        p = _payload()
        p["entry"][0]["changes"][0]["value"]["messages"][0] = {
            "id": "wamid.3",
            "from": "919000000000",
            "type": "document",
            "document": {"caption": "invoice", "mime_type": "application/pdf"},
        }
        (s,) = parse_webhook(p)
        assert s.has_media and s.media_mime == "application/pdf"

    def test_status_only_delivery_returns_empty(self) -> None:
        p = _payload()
        p["entry"][0]["changes"][0]["value"] = {"statuses": [{"id": "s1"}]}
        assert parse_webhook(p) == []

    def test_unsupported_type_dropped(self) -> None:
        p = _payload()
        p["entry"][0]["changes"][0]["value"]["messages"][0] = {
            "id": "wamid.4",
            "from": "919000000000",
            "type": "sticker",
        }
        assert parse_webhook(p) == []

    def test_bad_object_raises(self) -> None:
        with pytest.raises(WhatsAppWebhookError):
            parse_webhook({"object": "page"})


class TestVerificationHandshake:
    def test_challenge_echoed(self) -> None:
        assert (
            parse_verification(
                {"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "1158201444"}
            )
            == "1158201444"
        )

    def test_bad_mode_raises(self) -> None:
        with pytest.raises(WhatsAppWebhookError):
            parse_verification({"hub.mode": "unsubscribe", "hub.challenge": "1"})

    def test_token_checked_constant_time_path(self) -> None:
        verify_subscription_token("vt-token", _settings())
        with pytest.raises(WhatsAppWebhookError):
            verify_subscription_token("wrong", _settings())


class TestReply:
    def test_scam_reply_warns(self) -> None:
        assert "Do not pay" in build_reply("SCAM")

    def test_safe_reply_calm(self) -> None:
        assert build_reply("SAFE").startswith("✅")
