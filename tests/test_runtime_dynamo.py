"""Tests for the DynamoDB-backed graph store behind a fake client."""

from __future__ import annotations

from typing import Any

from gatehouse.runtime_dynamo import DynamoGraphStore


class FakeDynamo:
    """Records update_item calls; batch_get_item returns scripted items."""

    def __init__(self) -> None:
        self.updates: list[dict[str, Any]] = []
        self.items_by_pk: dict[str, dict[str, Any]] = {}
        self.fail_batch = False

    def update_item(self, **kwargs: Any) -> dict[str, Any]:
        from tests.conftest import assert_dynamo_grammar_safe

        assert_dynamo_grammar_safe(kwargs)
        self.updates.append(kwargs)
        return {}

    def batch_get_item(self, RequestItems: dict[str, Any]) -> dict[str, Any]:
        if self.fail_batch:
            raise RuntimeError("dynamo down")
        table = next(iter(RequestItems))
        keys = RequestItems[table]["Keys"]
        found = [self.items_by_pk[k["pk"]["S"]] for k in keys if k["pk"]["S"] in self.items_by_pk]
        return {"Responses": {table: found}}


def seeded_node(pk: str, taint: float, count: int, last_seen: int) -> dict[str, Any]:
    return {
        "pk": {"S": pk},
        "event_count": {"N": str(count)},
        "taint": {"N": str(taint)},
        "last_seen": {"N": str(last_seen)},
        "first_seen": {"N": str(last_seen)},
    }


HASH_A = "a" * 32  # schema floor is 16 chars; use a realistic hash length


class TestUpsert:
    def test_counter_write_then_taint_raise(self) -> None:
        client = FakeDynamo()
        store = DynamoGraphStore(client, "t")
        store.upsert_event([("VPA", "abc123")], taint_base=0.85, case_id="c1", now=1000)
        # Two writes per identifier: counters first, conditional taint second.
        assert len(client.updates) == 2
        first = client.updates[0]
        assert "ADD event_count" in first["UpdateExpression"]
        second = client.updates[1]
        assert "SET #t = :base" in second["UpdateExpression"]
        assert "attribute_not_exists(#t) OR #t < :base" in second["ConditionExpression"]
        assert second["ExpressionAttributeNames"] == {"#t": "taint"}

    def test_existing_higher_taint_condition_fails_silently(self) -> None:
        client = FakeDynamo()
        calls: list[dict[str, Any]] = []

        def boom(**kwargs: Any) -> dict[str, Any]:
            if kwargs.get("ConditionExpression"):
                raise RuntimeError("ConditionalCheckFailed")
            calls.append(kwargs)
            return {}

        client.update_item = boom  # type: ignore[method-assign]
        store = DynamoGraphStore(client, "t")
        store.upsert_event([("PHONE", "x")], taint_base=0.10, case_id="c9", now=5)
        # No exception escaped: condition loss is the happy path.


class TestQueryAndFinding:
    def test_query_maps_kind_from_pk(self) -> None:
        client = FakeDynamo()
        client.items_by_pk[f"ID#VPA#{HASH_A}"] = seeded_node(f"ID#VPA#{HASH_A}", 0.7, 3, 1_000_000)
        store = DynamoGraphStore(client, "t")
        ids = store.query([HASH_A])
        assert len(ids) == 1
        assert ids[0].kind == "VPA"
        assert ids[0].event_count == 3
        assert abs(ids[0].taint - 0.7) < 1e-6
        assert ids[0].coverage_note == "dynamo node store"

    def test_missing_identifier_returns_empty(self) -> None:
        store = DynamoGraphStore(FakeDynamo(), "t")
        assert store.query(["nope"]) == []

    def test_read_failure_degrades_to_empty(self) -> None:
        client = FakeDynamo()
        client.fail_batch = True
        store = DynamoGraphStore(client, "t")
        finding = store.finding_for([HASH_A])
        assert finding.unavailable is False
        assert finding.identifiers == []
        assert finding.prior_events == 0

    def test_finding_decay_lowers_old_taint(self) -> None:
        client = FakeDynamo()
        old_ts = 1_000  # long ago relative to 45-day decay constant
        client.items_by_pk[f"ID#VPA#{HASH_A}"] = seeded_node(f"ID#VPA#{HASH_A}", 0.9, 2, old_ts)
        store = DynamoGraphStore(client, "t")
        fresh = store.finding_for([HASH_A], now=old_ts + 60)
        stale = store.finding_for([HASH_A], now=old_ts + 200 * 86400)
        assert fresh.max_taint > stale.max_taint
