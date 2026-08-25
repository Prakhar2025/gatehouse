"""Dedupe: short-circuit repeat signals before they spend money (doc 05 section 5).

The contract:
- Idempotency key is (channel, household_id, content_hash).
- TTL is per channel: Telegram 72h default, email 7d, WhatsApp 72h. Configurable
  via settings, with sane defaults that match the doc.
- A hit returns the prior case id; the pipeline does not re-run.
- A miss records the case id so a subsequent forward of the same content hits.

Two backends behind one Protocol: in-memory for tests/dev, DynamoDB for prod.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Protocol


def content_hash(text: str) -> str:
    """Stable, short, URL-safe. Truncated SHA-256 is plenty for dedupe."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:32]


@dataclass(frozen=True)
class DedupeHit:
    """What we return when content was already seen."""

    case_id: str
    content_hash: str
    first_seen: float


class DedupeStore(Protocol):
    def check_and_record(
        self,
        channel: str,
        household_id: str,
        text: str,
        case_id: str,
        now: float | None = None,
    ) -> DedupeHit | None: ...


class InMemoryDedupeStore:
    """Process-local. Sufficient for unit tests, local dev, and the 50-send
    Journey A harness; not safe across processes or restarts."""

    def __init__(self, ttl_seconds_by_channel: dict[str, int] | None = None) -> None:
        self._ttl = ttl_seconds_by_channel or {
            "telegram": 72 * 3600,
            "whatsapp": 72 * 3600,
            "email": 7 * 24 * 3600,
            "api": 24 * 3600,
        }
        # key: (channel, household, content_hash) -> (case_id, first_seen)
        self._store: dict[tuple[str, str, str], tuple[str, float]] = {}

    def check_and_record(
        self,
        channel: str,
        household_id: str,
        text: str,
        case_id: str,
        now: float | None = None,
    ) -> DedupeHit | None:
        now_f = now if now is not None else time.time()
        ttl = self._ttl.get(channel, 72 * 3600)
        ch = content_hash(text)
        key = (channel, household_id, ch)
        existing = self._store.get(key)
        if existing is not None and now_f - existing[1] <= ttl:
            return DedupeHit(case_id=existing[0], content_hash=ch, first_seen=existing[1])
        self._store[key] = (case_id, now_f)
        return None


class DynamoDedupeStore:
    """DynamoDB-backed dedupe. One item per key, conditional write for atomicity."""

    def __init__(
        self, client: Any, table_name: str, ttl_seconds_by_channel: dict[str, int] | None = None
    ) -> None:
        self._client = client
        self._table = table_name
        self._ttl = ttl_seconds_by_channel or {
            "telegram": 72 * 3600,
            "whatsapp": 72 * 3600,
            "email": 7 * 24 * 3600,
            "api": 24 * 3600,
        }

    def check_and_record(
        self,
        channel: str,
        household_id: str,
        text: str,
        case_id: str,
        now: float | None = None,
    ) -> DedupeHit | None:
        now_f = now if now is not None else time.time()
        ttl = self._ttl.get(channel, 72 * 3600)
        ch = content_hash(text)
        pk = f"DEDUPE#{channel}#{household_id}#{ch}"
        # Conditional put: only if not present. If the put fails, read the
        # existing item and return its case id.
        try:
            self._client.put_item(
                TableName=self._table,
                Item={
                    "pk": {"S": pk},
                    "sk": {"S": "META"},
                    "case_id": {"S": case_id},
                    "first_seen": {"N": str(int(now_f))},
                    "expires_at": {"N": str(int(now_f + ttl))},
                },
                ConditionExpression="attribute_not_exists(pk)",
            )
        except Exception:
            resp = self._client.get_item(
                TableName=self._table, Key={"pk": {"S": pk}, "sk": {"S": "META"}}
            )
            item = resp.get("Item") or {}
            return DedupeHit(
                case_id=item.get("case_id", {}).get("S", ""),
                content_hash=ch,
                first_seen=float(item.get("first_seen", {}).get("N", "0")),
            )
        return None
