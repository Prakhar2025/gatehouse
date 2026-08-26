"""Tests for the binding store. Both backends, no network."""

from __future__ import annotations

from typing import Any

import pytest

from gatehouse.channels.binding import (
    AlreadyLinkedError,
    InMemoryBindingStore,
    InviteError,
    UnlinkedSenderError,
    verify_sender,
)


class TestInMemoryBindingStore:
    def test_issue_invite_returns_six_char_code(self) -> None:
        store = InMemoryBindingStore()
        invite = store.issue_invite("fam-1", now=1000.0)
        assert len(invite.code) == 6
        assert invite.household_id == "fam-1"
        assert invite.expires_at == 1000.0 + 600.0

    def test_consume_invite_creates_binding(self) -> None:
        store = InMemoryBindingStore()
        invite = store.issue_invite("fam-1", now=1000.0)
        binding = store.consume_invite(invite.code, "telegram", "5500012", now=1001.0)
        assert binding.household_id == "fam-1"
        assert binding.channel == "telegram"
        assert binding.channel_id == "5500012"
        assert binding.linked_at == 1001.0

    def test_invite_single_use(self) -> None:
        store = InMemoryBindingStore()
        invite = store.issue_invite("fam-1", now=1000.0)
        store.consume_invite(invite.code, "telegram", "5500012", now=1001.0)
        with pytest.raises(InviteError):
            store.consume_invite(invite.code, "telegram", "5500013", now=1002.0)

    def test_expired_invite_rejected(self) -> None:
        store = InMemoryBindingStore(ttl_seconds=60)
        invite = store.issue_invite("fam-1", now=1000.0)
        with pytest.raises(InviteError):
            store.consume_invite(invite.code, "telegram", "5500012", now=1200.0)

    def test_unknown_code_rejected(self) -> None:
        store = InMemoryBindingStore()
        with pytest.raises(InviteError):
            store.consume_invite("ZZZZZZ", "telegram", "5500012", now=1000.0)

    def test_channel_id_cannot_bind_twice(self) -> None:
        store = InMemoryBindingStore()
        invite_a = store.issue_invite("fam-1", now=1000.0)
        store.consume_invite(invite_a.code, "telegram", "5500012", now=1001.0)
        invite_b = store.issue_invite("fam-2", now=1000.0)
        with pytest.raises(AlreadyLinkedError):
            store.consume_invite(invite_b.code, "telegram", "5500012", now=1001.0)

    def test_lookup_returns_binding(self) -> None:
        store = InMemoryBindingStore()
        invite = store.issue_invite("fam-1", now=1000.0)
        store.consume_invite(invite.code, "telegram", "5500012", now=1001.0)
        binding = store.lookup("telegram", "5500012")
        assert binding is not None and binding.household_id == "fam-1"

    def test_lookup_returns_none_when_absent(self) -> None:
        store = InMemoryBindingStore()
        assert store.lookup("telegram", "5500012") is None

    def test_unlink_removes_binding(self) -> None:
        store = InMemoryBindingStore()
        invite = store.issue_invite("fam-1", now=1000.0)
        store.consume_invite(invite.code, "telegram", "5500012", now=1001.0)
        assert store.unlink("telegram", "5500012") is True
        assert store.lookup("telegram", "5500012") is None
        assert store.unlink("telegram", "5500012") is False


class TestVerifySender:
    def test_returns_binding_when_linked(self) -> None:
        store = InMemoryBindingStore()
        invite = store.issue_invite("fam-1", now=1000.0)
        store.consume_invite(invite.code, "telegram", "5500012", now=1001.0)
        binding = verify_sender(store, "telegram", "5500012")
        assert binding.household_id == "fam-1"

    def test_raises_for_unlinked_sender(self) -> None:
        store = InMemoryBindingStore()
        with pytest.raises(UnlinkedSenderError):
            verify_sender(store, "telegram", "9999")


class _FakeConditionFailError(Exception):
    pass


class _FakeDynamo:
    """In-memory boto3 stand-in for the binding store, with condition semantics."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, str], dict[str, Any]] = {}
        self.puts: list[dict[str, Any]] = []
        self.updates: list[dict[str, Any]] = []

    def put_item(self, **kwargs: Any) -> dict[str, Any]:
        self.puts.append(kwargs)
        item = kwargs["Item"]
        key = (item["pk"]["S"], item["sk"]["S"])
        if kwargs.get("ConditionExpression") == "attribute_not_exists(pk)" and key in self._items:
            raise _FakeConditionFailError("ConditionalCheckFailed")
        self._items[key] = item
        return {}

    def get_item(self, **kwargs: Any) -> dict[str, Any]:
        item = self._items.get((kwargs["Key"]["pk"]["S"], kwargs["Key"]["sk"]["S"]))
        return {"Item": item} if item else {}

    def update_item(self, **kwargs: Any) -> dict[str, Any]:
        self.updates.append(kwargs)
        from tests.conftest import assert_dynamo_grammar_safe

        assert_dynamo_grammar_safe(kwargs)
        key = (kwargs["Key"]["pk"]["S"], kwargs["Key"]["sk"]["S"])
        item = self._items.get(key)
        if item is None:
            raise _FakeConditionFailError("ConditionalCheckFailed")
        if kwargs.get("ConditionExpression", "").startswith("attribute_exists"):
            names = kwargs.get("ExpressionAttributeNames", {})
            attr = names.get("#c", "consumed")
            if item.get(attr, {}).get("BOOL", False):
                raise _FakeConditionFailError("ConditionalCheckFailed")
            item[attr] = kwargs["ExpressionAttributeValues"][":true"]
        self._items[key] = item
        return {"Attributes": item}

    def delete_item(self, **kwargs: Any) -> dict[str, Any]:
        key = (kwargs["Key"]["pk"]["S"], kwargs["Key"]["sk"]["S"])
        if key in self._items:
            item = self._items.pop(key)
            return {"Attributes": item}
        return {}


class TestDynamoBindingStore:
    def test_issue_and_consume_round_trip(self) -> None:
        from gatehouse.channels.binding import DynamoBindingStore

        fake = _FakeDynamo()
        store = DynamoBindingStore(fake, "gatehouse-bindings", ttl_seconds=60)
        invite = store.issue_invite("fam-1", now=1000.0)
        binding = store.consume_invite(invite.code, "telegram", "5500012", now=1001.0)
        assert binding.household_id == "fam-1"
        assert binding.linked_at == 1001.0

    def test_consume_after_consume_rejected(self) -> None:
        from gatehouse.channels.binding import DynamoBindingStore

        fake = _FakeDynamo()
        store = DynamoBindingStore(fake, "gatehouse-bindings")
        invite = store.issue_invite("fam-1", now=1000.0)
        store.consume_invite(invite.code, "telegram", "5500012", now=1001.0)
        with pytest.raises(_FakeConditionFailError):
            store.consume_invite(invite.code, "telegram", "5500013", now=1002.0)

    def test_condition_failure_translates_to_already_linked(self) -> None:
        """The live backend raises botocore's condition error; the runtime
        contract expects AlreadyLinkedError. Both backends must agree."""
        from botocore.exceptions import ClientError

        from gatehouse.channels.binding import AlreadyLinkedError, DynamoBindingStore

        class FakeClient(_FakeDynamo):
            def put_item(self, **kwargs: Any) -> dict[str, Any]:
                pk = kwargs.get("Item", {}).get("pk", {}).get("S", "")
                if pk.startswith("BINDING#"):
                    raise ClientError(
                        {
                            "Error": {
                                "Code": "ConditionalCheckFailedException",
                                "Message": "conditional request failed",
                            }
                        },
                        "PutItem",
                    )
                return super().put_item(**kwargs)

        fake = FakeClient()
        store = DynamoBindingStore(fake, "gatehouse-bindings")
        invite = store.issue_invite("fam-1", now=1000.0)
        with pytest.raises(AlreadyLinkedError):
            store.consume_invite(invite.code, "telegram", "5500099", now=1001.0)

    def test_lookup_and_unlink(self) -> None:
        from gatehouse.channels.binding import DynamoBindingStore

        fake = _FakeDynamo()
        store = DynamoBindingStore(fake, "gatehouse-bindings")
        invite = store.issue_invite("fam-1", now=1000.0)
        store.consume_invite(invite.code, "telegram", "5500012", now=1001.0)
        assert store.lookup("telegram", "5500012") is not None
        assert store.unlink("telegram", "5500012") is True
        assert store.lookup("telegram", "5500012") is None
