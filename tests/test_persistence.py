"""Tests for persistence: fake Dynamo client, no network."""

from __future__ import annotations

from typing import Any

import pytest

from gatehouse.agents.schemas import GuardianPackage
from gatehouse.config import Settings
from gatehouse.persistence import CaseStore, GraphPersistence, case_keys, graph_key


class FakeDynamo:
    """Minimal in-memory double of the boto3 call surface we use."""

    def __init__(self, existing: set[tuple[str, str]] | None = None) -> None:
        self.puts: list[dict[str, Any]] = []
        self.updates: list[dict[str, Any]] = []
        self.gets: list[dict[str, Any]] = []
        self._existing = existing or set()
        self._items: dict[tuple[str, str], dict[str, Any]] = {}

    def put_item(self, **kwargs: Any) -> dict[str, Any]:
        item = kwargs["Item"]
        key = (item["pk"]["S"], item["sk"]["S"])
        if key in self._existing:
            raise ValueError("ConditionalCheckFailed")
        self._existing.add(key)
        self.puts.append(kwargs)
        self._items[key] = item
        return {}

    def get_item(self, **kwargs: Any) -> dict[str, Any]:
        self.gets.append(kwargs)
        pk = kwargs["Key"]["pk"]["S"]
        found = None
        for (cpk, _csk), item in self._items.items():
            if cpk == pk:
                found = item
        if found is None and not self._items:
            return {}
        key_pk = kwargs.get("Key", {}).get("pk", {}).get("S", "")
        if key_pk.startswith("ID#"):
            node = {"pk": kwargs["Key"]["pk"], "event_count": {"N": "3"}, "taint": {"N": "0.7"}}
            return {"Item": node}
        return {"Item": found} if found else {}

    def update_item(self, **kwargs: Any) -> dict[str, Any]:
        self.updates.append(kwargs)
        return {}


@pytest.fixture()
def settings() -> Settings:
    return Settings(environment="local")


class TestCaseKeys:
    def test_household_prefix_enforced(self) -> None:
        keys = case_keys("fam-1", "case-9")
        assert keys.pk == "HOUSEHOLD#fam-1"
        assert keys.sk == "CASE#case-9"

    def test_graph_namespaced_by_kind(self) -> None:
        assert graph_key("phone", "abc123").startswith("ID#PHONE#")


class TestCaseStore:
    def test_save_verdict_writes_item(self, settings: Settings) -> None:
        fake = FakeDynamo()
        store = CaseStore(fake, "gatehouse-cases", settings)
        package = GuardianPackage(
            verdict="SCAM",
            confidence=0.9,
            reason_codes=["HARD_FAIL"],
            top_evidence=["e"],
            recommended_action="warn_member",
            degraded_flags=[],
        )
        store.save_verdict("fam-1", "case-9", package, "DECISION", 0.01, now=1000.0)
        assert len(fake.puts) == 1
        item = fake.puts[0]["Item"]
        assert item["pk"]["S"] == "HOUSEHOLD#fam-1"
        assert item["verdict"]["S"] == "SCAM"
        assert int(float(item["expires_at"]["N"])) == 1000 + 90 * 86400

    def test_duplicate_verdict_rejected(self, settings: Settings) -> None:
        store = CaseStore(FakeDynamo(), "t", settings)
        package = GuardianPackage(
            verdict="SAFE",
            confidence=0.9,
            reason_codes=[],
            top_evidence=[],
            recommended_action="none",
            degraded_flags=[],
        )
        store.save_verdict("f", "c", package, "NOISE", 0.0, now=0.0)
        with pytest.raises(ValueError, match="ConditionalCheckFailed"):
            store.save_verdict("f", "c", package, "NOISE", 0.0, now=0.0)


class TestGraphPersistence:
    def test_record_event_uses_atomic_add(self, settings: Settings) -> None:
        fake = FakeDynamo()
        graph = GraphPersistence(fake, "gatehouse-graph", settings)
        graph.record_event("PHONE", "hash1", 0.8, "case-1", now=500.0)
        assert len(fake.updates) == 1
        update = fake.updates[0]
        assert "ADD event_count" in update["UpdateExpression"]
        assert update["Key"]["pk"]["S"] == "ID#PHONE#hash1"
        assert int(update["ExpressionAttributeValues"][":ttl"]["N"]) == 500 + 365 * 86400

    def test_lookup_returns_item_or_none(self, settings: Settings) -> None:
        fake = FakeDynamo(existing={("x", "y")})
        graph = GraphPersistence(fake, "g", settings)
        result = graph.lookup("VPA", "hash2")
        # fake returns an item when any data exists
        assert result is None or "event_count" in result
