"""Tests for the dedupe store. Both backends, no network."""

from __future__ import annotations

from typing import Any

from gatehouse.channels.dedupe import (
    DynamoDedupeStore,
    InMemoryDedupeStore,
    content_hash,
)


class TestContentHash:
    def test_deterministic(self) -> None:
        assert content_hash("hello") == content_hash("hello")

    def test_strips_whitespace(self) -> None:
        assert content_hash("  hello  ") == content_hash("hello")

    def test_different_text_different_hash(self) -> None:
        assert content_hash("hello") != content_hash("world")

    def test_unicode_preserved(self) -> None:
        assert content_hash("नमस्ते") != content_hash("hello")


class TestInMemoryDedupe:
    def test_first_call_returns_none(self) -> None:
        store = InMemoryDedupeStore()
        result = store.check_and_record("telegram", "fam-1", "msg", "case-1", now=1000.0)
        assert result is None

    def test_second_call_returns_first_case(self) -> None:
        store = InMemoryDedupeStore()
        store.check_and_record("telegram", "fam-1", "msg", "case-1", now=1000.0)
        result = store.check_and_record("telegram", "fam-1", "msg", "case-2", now=1001.0)
        assert result is not None
        assert result.case_id == "case-1"

    def test_different_household_not_a_duplicate(self) -> None:
        store = InMemoryDedupeStore()
        store.check_and_record("telegram", "fam-1", "msg", "case-1", now=1000.0)
        result = store.check_and_record("telegram", "fam-2", "msg", "case-2", now=1001.0)
        assert result is None

    def test_different_channel_not_a_duplicate(self) -> None:
        store = InMemoryDedupeStore()
        store.check_and_record("telegram", "fam-1", "msg", "case-1", now=1000.0)
        result = store.check_and_record("whatsapp", "fam-1", "msg", "case-2", now=1001.0)
        assert result is None

    def test_ttl_expiry_resets(self) -> None:
        store = InMemoryDedupeStore(ttl_seconds_by_channel={"telegram": 60})
        store.check_and_record("telegram", "fam-1", "msg", "case-1", now=1000.0)
        result = store.check_and_record("telegram", "fam-1", "msg", "case-2", now=2000.0)
        assert result is None

    def test_email_ttl_longer_than_telegram(self) -> None:
        store = InMemoryDedupeStore()
        # Telegram default 72h
        store.check_and_record("telegram", "fam-1", "msg", "case-1", now=0.0)
        # Same content via email 24h later is a fresh case under email TTL
        result = store.check_and_record("email", "fam-1", "msg", "case-2", now=24 * 3600)
        assert result is None


class _FakeDynamo:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], dict[str, Any]] = {}

    def put_item(self, **kwargs: Any) -> dict[str, Any]:
        item = kwargs["Item"]
        key = (item["pk"]["S"], item["sk"]["S"])
        if kwargs.get("ConditionExpression") == "attribute_not_exists(pk)" and key in self._items:
            raise RuntimeError("ConditionalCheckFailed")
        self._items[key] = item
        return {}

    def get_item(self, **kwargs: Any) -> dict[str, Any]:
        item = self._items.get((kwargs["Key"]["pk"]["S"], kwargs["Key"]["sk"]["S"]))
        return {"Item": item} if item else {}


class TestDynamoDedupe:
    def test_first_call_records(self) -> None:
        fake = _FakeDynamo()
        store = DynamoDedupeStore(fake, "gatehouse-dedupe")
        result = store.check_and_record("telegram", "fam-1", "msg", "case-1", now=1000.0)
        assert result is None
        assert len(fake._items) == 1

    def test_second_call_returns_prior_case(self) -> None:
        fake = _FakeDynamo()
        store = DynamoDedupeStore(fake, "gatehouse-dedupe")
        store.check_and_record("telegram", "fam-1", "msg", "case-1", now=1000.0)
        result = store.check_and_record("telegram", "fam-1", "msg", "case-2", now=1001.0)
        assert result is not None
        assert result.case_id == "case-1"
