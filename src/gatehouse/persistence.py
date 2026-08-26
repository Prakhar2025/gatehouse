"""DynamoDB persistence: single-table design behind a store protocol (doc 06).

Tables (deployed via SAM, accessed here):
- gatehouse-cases:   one item per case (PK: HOUSEHOLD#<hid>#CASE#<cid>),
                     TTL on expires_at, stream-free in v1
- gatehouse-graph:   hashed identifier nodes (PK: ID#<kind>#<hash>)

Access rules (docs/18 section 2): household prefix on every key, no scans in
hot paths, conditional writes for idempotency, TTL everywhere.

The client is injected; unit tests use fakes, prod uses boto3. No network in
unit tests, ever.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol

from gatehouse.agents.schemas import GuardianPackage
from gatehouse.config import Settings

_CASE_TTL_DAYS = 90
_GRAPH_TTL_DAYS = 365


class DynamoClient(Protocol):
    """The slice of boto3 we use; fakes implement the same three methods."""

    def put_item(self, **kwargs: Any) -> dict[str, Any]: ...

    def get_item(self, **kwargs: Any) -> dict[str, Any]: ...

    def update_item(self, **kwargs: Any) -> dict[str, Any]: ...


@dataclass(frozen=True)
class CaseKeys:
    """Deterministic keys for one case item."""

    pk: str
    sk: str


def case_keys(household_id: str, case_id: str) -> CaseKeys:
    return CaseKeys(pk=f"HOUSEHOLD#{household_id}", sk=f"CASE#{case_id}")


def graph_key(kind: str, hashed_value: str) -> str:
    return f"ID#{kind.upper()}#{hashed_value}"


def _ttl(days: int, now: float | None = None) -> int:
    return int((now if now is not None else time.time()) + days * 86400)


class CaseStore:
    """Case persistence: write-once per verdict, idempotent by case id."""

    def __init__(self, client: DynamoClient, table_name: str, settings: Settings) -> None:
        self._client = client
        self._table = table_name
        self._settings = settings

    def save_verdict(
        self,
        household_id: str,
        case_id: str,
        package: GuardianPackage,
        triage_class: str,
        spend_usd: float,
        now: float | None = None,
    ) -> dict[str, Any]:
        """Persist the guardian package. ConditionExpression makes retries safe."""
        keys = case_keys(household_id, case_id)
        item: dict[str, Any] = {
            "pk": {"S": keys.pk},
            "sk": {"S": keys.sk},
            "verdict": {"S": package.verdict},
            "confidence": {"N": str(package.confidence)},
            "triage_class": {"S": triage_class},
            "reason_codes": {"SS": package.reason_codes or ["NONE"]},
            "spend_usd": {"N": str(spend_usd)},
            "degraded_flags": {"SS": package.degraded_flags or ["NONE"]},
            "expires_at": {"N": str(_ttl(_CASE_TTL_DAYS, now))},
        }
        return self._client.put_item(
            TableName=self._table,
            Item=item,
            ConditionExpression="attribute_not_exists(pk) AND attribute_not_exists(sk)",
        )


class GraphPersistence:
    """Hashed-identifier node persistence with event counting."""

    def __init__(self, client: DynamoClient, table_name: str, settings: Settings) -> None:
        self._client = client
        self._table = table_name
        self._settings = settings

    def record_event(
        self, kind: str, hashed_value: str, taint: float, case_id: str, now: float | None = None
    ) -> dict[str, Any]:
        """Upsert one identifier node; ADD is atomic under concurrency."""
        ttl = _ttl(_GRAPH_TTL_DAYS, now)
        return self._client.update_item(
            TableName=self._table,
            Key={"pk": {"S": graph_key(kind, hashed_value)}},
            UpdateExpression=(
                "ADD event_count :one, ttl_x :ttl SET last_case = :c, "
                "#t = if_not_exists(#t, :zero), first_seen = if_not_exists(first_seen, :now)"
            ),
            # taint is a DynamoDB reserved keyword: never a bare name.
            ExpressionAttributeNames={"#t": "taint"},
            ExpressionAttributeValues={
                ":one": {"N": "1"},
                ":ttl": {"N": str(ttl)},
                ":c": {"S": case_id},
                ":zero": {"N": "0"},
                ":now": {"N": str(int(now if now is not None else time.time()))},
                ":ttl_x": {"N": str(ttl)},
            },
        )

    def lookup(self, kind: str, hashed_value: str) -> dict[str, Any] | None:
        """Return the raw node item if present."""
        response = self._client.get_item(
            TableName=self._table, Key={"pk": {"S": graph_key(kind, hashed_value)}}
        )
        item = response.get("Item")
        return dict(item) if item else None
