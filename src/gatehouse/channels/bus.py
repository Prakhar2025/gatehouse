"""EventBridge publisher: intake events reach the investigation bus (doc 05 section 5).

One job: take an intake envelope, sign it, and put it on the bus with the
exact-once identity the pipeline dedupes on. The PutEvents call is batched
(10 per call, the service limit) and per-entry failures are counted so the
caller can requeue honestly instead of pretending everything landed.

The client is injected: tests pass a fake, prod passes boto3. No SDK import
at module scope keeps this module cheap to load inside Lambda.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

DETAIL_TYPE = "gatehouse.intake.signal"
SOURCE = "gatehouse.channels"
BATCH_LIMIT = 10  # EventBridge PutEvents entries per call


class PublishError(Exception):
    """Raised when a publish call itself fails (client error, throttling)."""


@dataclass(frozen=True)
class PublishResult:
    """Honest accounting of one publish attempt."""

    published: int = 0
    failed: int = 0


def _entry(envelope: dict[str, Any], signature: str) -> dict[str, Any]:
    """One PutEvents entry; the signed envelope rides in Detail."""
    detail = dict(envelope)
    detail["signature"] = signature  # consumer verifies before parsing text
    return {
        "Source": SOURCE,
        "DetailType": DETAIL_TYPE,
        "Detail": json.dumps(detail, separators=(",", ":"), ensure_ascii=False),
        "EventBusName": str(envelope.get("event_bus_name", "default")),
        # Traceability arm without leaking message content.
        "Resources": [envelope["event_id"]],
    }


class EventBridgePublisher:
    """Publishes signed intake envelopes onto the shared event bus."""

    def __init__(self, client: Any, signing_key: str) -> None:
        self._client = client
        self._key = signing_key

    def publish(self, envelopes: list[dict[str, Any]]) -> PublishResult:
        """Publish envelopes in batches of 10, signing each one here.

        Signatures are always computed inside publish so callers cannot
        accidentally put unsigned events on the bus.
        """
        from gatehouse.channels.events import sign_event

        published = 0
        failed = 0
        for start in range(0, len(envelopes), BATCH_LIMIT):
            batch = envelopes[start : start + BATCH_LIMIT]
            entries = [_entry(env, sign_event(env, self._key)) for env in batch]
            response = self._client.put_events(Entries=entries)
            for resp_entry in response.get("Entries", []):
                if "EventId" in resp_entry:
                    published += 1
                else:
                    failed += 1
        return PublishResult(published=published, failed=failed)
