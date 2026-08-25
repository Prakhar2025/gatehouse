"""Signed event envelope: the contract between intake and investigation (doc 05 section 5).

Every accepted inbound signal, regardless of channel, leaves the gateway as one
canonical event:
- event_id is channel + content hash + household, so retries collapse naturally.
- The body carries the bounded working copy of untrusted text, never more than
  the pipeline will spend on.
- An HMAC signature covers the canonical JSON; the consumer verifies before
  parsing anything, mirroring the webhook-verification discipline at the edge.

Stdlib only: no bus SDK import here. The EventBridge PutEvents call happens in
the deployment layer (P4); this module owns the wire format and its integrity.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any

TEXT_CAP = 4000


@dataclass(frozen=True)
class GatewayEvent:
    """The normalized signal every channel parser must produce."""

    channel: str
    household_id: str
    sender_name: str
    text: str
    is_forward: bool
    received_at: float


def content_hash(text: str) -> str:
    """Stable short hash of the normalized text; shared with the dedupe layer."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:32]


def event_id(event: GatewayEvent) -> str:
    """Doc 05 section 5 identity: channel + content hash + household."""
    return f"{event.channel}#{content_hash(event.text)}#{event.household_id}"


def build_envelope(event: GatewayEvent) -> dict[str, Any]:
    """Canonical JSON-ready envelope for the bus."""
    return {
        "event_id": event_id(event),
        "channel": event.channel,
        "household_id": event.household_id,
        "sender_name": event.sender_name,
        "is_forward": event.is_forward,
        "content_hash": content_hash(event.text),
        "received_at": event.received_at or time.time(),
        "text": event.text[:TEXT_CAP],
    }


def _canonical(payload: dict[str, Any]) -> bytes:
    """Deterministic serialization; any key order change would break signatures."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def sign_event(envelope: dict[str, Any], signing_key: str) -> str:
    """HMAC-SHA256 over the canonical body; hex-encoded for transport."""
    return hmac.new(signing_key.encode("utf-8"), _canonical(envelope), hashlib.sha256).hexdigest()


def verify_event(envelope: dict[str, Any], signature: str | None, signing_key: str) -> bool:
    """Constant-time check; consumers refuse unsigned or mismatched events."""
    if not signature:
        return False
    return hmac.compare_digest(sign_event(envelope, signing_key), signature)
