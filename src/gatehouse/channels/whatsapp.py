"""WhatsApp webhook: Meta Cloud API intake behind the channel flag (doc 05 section 3).

v1 scope per doc 05:
- Members forward to the Gatehouse WhatsApp number; Meta delivers a webhook.
- Verdicts reply inside the 24h customer service window opened by the forward.
- Media at launch: text, image, document. This skeleton handles text and
  captions; image/document OCR lands with the normalize stage wiring.
- Guardian escalations never fan out over WhatsApp in v1.

The whole channel is gated by GATEHOUSE_WHATSAPP_ENABLED: when false, the
webhook still answers Meta's verification handshake (so Meta does not disable
the subscription) but rejects every inbound message before parsing.

Signature discipline mirrors Telegram's secret header: Meta signs each request
with X-Hub-Signature-256 as sha256=<hex> of HMAC(app_secret, raw body). We
compare constant-time against our configured app secret.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any

from gatehouse.config import Settings


class WhatsAppWebhookError(Exception):
    """Raised for any WhatsApp request that must not be processed."""


@dataclass(frozen=True)
class WhatsAppSignal:
    """The minimal validated shape from one Meta webhook payload."""

    message_id: str
    phone_number: str
    sender_name: str
    text: str
    is_forward: bool
    has_media: bool
    media_mime: str | None


def verify_signature(header_value: str | None, raw_body: bytes, settings: Settings) -> None:
    """Meta x-hub-signature-256 check; mismatch raises WhatsAppWebhookError."""
    if not settings.whatsapp_app_secret:
        raise WhatsAppWebhookError("whatsapp app secret not configured")
    if not header_value or not header_value.startswith("sha256="):
        raise WhatsAppWebhookError("missing whatsapp signature")
    expected = (
        "sha256="
        + hmac.new(
            settings.whatsapp_app_secret.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
    )
    if not hmac.compare_digest(header_value, expected):
        raise WhatsAppWebhookError("bad whatsapp signature")


def parse_webhook(payload: dict[str, Any]) -> list[WhatsAppSignal]:
    """Extract every usable signal from one webhook delivery.

    Meta batches multiple contacts/messages per delivery; we return one signal
    per message and silently drop statuses-only deliveries. Raises
    WhatsAppWebhookError only for structurally invalid payloads.
    """
    object_type = payload.get("object")
    if object_type != "whatsapp_business_account":
        raise WhatsAppWebhookError("unexpected webhook object")

    entries = payload.get("entry") or []
    signals: list[WhatsAppSignal] = []
    for entry in entries if isinstance(entries, list) else []:
        changes = entry.get("changes") or []
        for change in changes if isinstance(changes, list) else []:
            value = change.get("value") or {}
            metadata = value.get("metadata") or {}
            display_phone = str(metadata.get("display_phone_number", ""))
            messages = value.get("messages") or []
            for msg in messages if isinstance(messages, list) else []:
                mtype = str(msg.get("type", ""))
                text_part = ""
                media_mime: str | None = None
                if mtype == "text":
                    text_obj = msg.get("text") or {}
                    text_part = str(text_obj.get("body", ""))
                elif mtype == "image":
                    img = msg.get("image") or {}
                    text_part = str(img.get("caption", ""))
                    media_mime = "image/jpeg"
                elif mtype == "document":
                    doc = msg.get("document") or {}
                    text_part = str(doc.get("caption", ""))
                    media_mime = str(doc.get("mime_type", "")) or "application/octet-stream"
                elif mtype == "button":
                    text_part = str((msg.get("button") or {}).get("text", ""))
                else:
                    continue  # unsupported type at launch; dropped honestly

                sender = msg.get("from", "")
                profile_name = ""
                contacts = value.get("contacts") or []
                if contacts and isinstance(contacts, list):
                    profile_name = str(((contacts[0] or {}).get("profile") or {}).get("name", ""))

                forwarded = True  # a member forwarding INTO Gatehouse is the v1 flow
                signals.append(
                    WhatsAppSignal(
                        message_id=str(msg.get("id", "")),
                        phone_number=display_phone,
                        sender_name=profile_name[:40] or str(sender)[:40],
                        text=text_part[:4000],
                        is_forward=forwarded,
                        has_media=mtype in ("image", "document"),
                        media_mime=media_mime,
                    )
                )
    return signals


def parse_verification(payload: dict[str, Any]) -> str:
    """Meta subscription handshake: echo hub.challenge or raise."""
    mode = payload.get("hub.mode")
    challenge = payload.get("hub.challenge")
    if mode != "subscribe" or not isinstance(challenge, (str, int)):
        raise WhatsAppWebhookError("invalid verification handshake")
    return str(challenge)


def verify_subscription_token(token: str | None, settings: Settings) -> None:
    """Constant-time compare of the verify token configured at signup."""
    expected = settings.whatsapp_verify_token
    if not expected:
        raise WhatsAppWebhookError("whatsapp verify token not configured")
    if not token or not hmac.compare_digest(token, expected):
        raise WhatsAppWebhookError("bad whatsapp verify token")


def build_reply(verdict: str) -> str:
    """Member-facing WhatsApp reply inside the 24h service window."""
    if verdict == "SCAM":
        return (
            "🚨 This looks like a scam. Do not pay, click, or share any OTP. "
            "Your guardian has the full evidence."
        )
    if verdict == "SUSPICIOUS":
        return (
            "⚠️ Some warning signs found. Checking deeper: hold any payment until "
            "your guardian confirms."
        )
    return "✅ Checked: nothing harmful found here."
