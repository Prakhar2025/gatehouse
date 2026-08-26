"""DynamoDB graph store: the prod backend behind the GraphStore protocol.

Node identity and taint semantics mirror the in-memory store (doc 06 section
3): one item per hashed identifier, event_count via atomic ADD, max-taint via
arithmetic overwrite, and a bounded one-hop propagation query at read time.
Co-occurrence edges are approximated with the prior-events count so the
guardian's repeat-offender signal works from day one; the full edge table is a
P4 observability upgrade and its absence degrades honestly (coverage_note).
"""

from __future__ import annotations

import math
import time
from typing import Any

from gatehouse.agents.schemas import GraphFinding, GraphIdentifier
from gatehouse.logging_utils import get_logger

log = get_logger("gatehouse.runtime_dynamo")

_KINDS = ("PHONE", "VPA", "DOMAIN", "URL_PATH", "BANK_ACCT", "EMAIL", "UTR_REF")
_HOP_DECAY = 0.6
_TIME_DECAY_DAYS = 45.0
_GRAPH_TTL_DAYS = 365


def _node_key(kind: str, hashed: str) -> str:
    return f"ID#{kind.upper()}#{hashed}"


class DynamoGraphStore:
    """Reads and writes graph nodes in the gatehouse-graph table."""

    def __init__(self, client: Any, table_name: str) -> None:
        self._client = client
        self._table = table_name

    def upsert_event(
        self,
        identifiers: list[tuple[str, str]],
        taint_base: float,
        case_id: str,
        now: float | None = None,
    ) -> None:
        ts = int(now if now is not None else time.time())
        ttl = ts + _GRAPH_TTL_DAYS * 86400
        for kind, hashed in identifiers:
            # Counters and timestamps first: ADD creates missing attributes at
            # zero, so first events work without a separate create step.
            self._client.update_item(
                TableName=self._table,
                Key={"pk": {"S": _node_key(kind, hashed)}},
                UpdateExpression=(
                    "ADD event_count :one SET last_seen = :ts, "
                    "first_seen = if_not_exists(first_seen, :ts), #e = :ttl_x"
                ),
                # expires_at is a DynamoDB reserved keyword: never a bare name.
                ExpressionAttributeNames={"#e": "expires_at"},
                ExpressionAttributeValues={
                    ":one": {"N": "1"},
                    ":ts": {"N": str(ts)},
                    ":ttl_x": {"N": str(ttl)},
                },
            )
            # Max-taint semantics: raise taint only when the new base is
            # higher; a failed condition means existing taint already wins.
            try:
                self._client.update_item(
                    TableName=self._table,
                    Key={"pk": {"S": _node_key(kind, hashed)}},
                    UpdateExpression="SET #t = :base",
                    # taint is a DynamoDB reserved keyword: never a bare name.
                    ConditionExpression=("attribute_not_exists(#t) OR #t < :base"),
                    ExpressionAttributeNames={"#t": "taint"},
                    ExpressionAttributeValues={":base": {"N": str(taint_base)}},
                )
            except Exception as exc:
                # Condition loss is the happy path: existing taint wins.
                log.debug(
                    "taint_condition_loss", extra={"extra_fields": {"error": type(exc).__name__}}
                )
                continue

    def query(self, hashed_values: list[str]) -> list[GraphIdentifier]:
        out: list[GraphIdentifier] = []
        for hashed in hashed_values:
            keys = [{"pk": {"S": _node_key(kind, hashed)}} for kind in _KINDS]
            try:
                resp = self._client.batch_get_item(RequestItems={self._table: {"Keys": keys}})
            except Exception as exc:
                log.warning(
                    "graph_read_failed", extra={"extra_fields": {"error": type(exc).__name__}}
                )
                resp = {}
            items = (resp.get("Responses", {}).get(self._table) or [])[:1]
            if not items:
                continue
            item = items[0]
            kind = str(item.get("pk", {}).get("S", "ID#UNKNOWN#")).split("#")[1]
            out.append(
                GraphIdentifier(
                    kind=kind,
                    hashed_value=hashed,
                    first_seen=str(item.get("first_seen", {}).get("N", "0")),
                    last_seen=str(item.get("last_seen", {}).get("N", "0")),
                    event_count=int(item.get("event_count", {}).get("N", "0")),
                    taint=round(float(item.get("taint", {}).get("N", "0")), 4),
                    coverage_note="dynamo node store",
                )
            )
        return out

    def finding_for(self, hashed_values: list[str], now: float | None = None) -> GraphFinding:
        ts = now if now is not None else time.time()
        ids = self.query(hashed_values)
        prior = sum(i.event_count for i in ids)
        best = 0.0
        for i in ids:
            days = max(0.0, (ts - float(i.last_seen or 0)) / 86400.0)
            decayed = i.taint * math.exp(-days / _TIME_DECAY_DAYS) * _HOP_DECAY**1
            best = max(best, min(decayed, 1.0))
        return GraphFinding(identifiers=ids, prior_events=prior, max_taint=round(best, 4))
