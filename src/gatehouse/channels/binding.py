"""Member-to-household binding store (doc 05 section 2).

Contract:
- A chat id (Telegram), phone (WhatsApp), or email address maps to a household
  id (or is rejected as unlinked).
- Bindings are created with a short-lived invite code; codes expire.
- Unlinked senders receive a refusal, never a case, never a model call.
- The store is the source of truth for "is this sender allowed to deliver a
  signal to the household?"; everything downstream trusts the boolean.

Two implementations:
- InMemoryBindingStore: unit tests, local dev, soak runs.
- DynamoBindingStore: production, behind the same Protocol so the call site
  never knows the difference.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Any, Protocol

# 10 minutes is enough to type the code on the phone; long enough to survive
# a brief Telegram outage, short enough to limit phishing window.
DEFAULT_INVITE_TTL_SECONDS = 600


@dataclass(frozen=True)
class InviteCode:
    """A one-shot code that links a future chat id to a household."""

    code: str
    household_id: str
    expires_at: float
    consumed: bool = False


@dataclass(frozen=True)
class Binding:
    """The durable fact: this channel-side identity talks for this household."""

    channel: str  # telegram | whatsapp | email
    channel_id: str  # chat_id as string for portability across channels
    household_id: str
    linked_at: float


class BindingStore(Protocol):
    """The slice of binding behavior every backend must provide."""

    def issue_invite(self, household_id: str, now: float | None = None) -> InviteCode: ...
    def consume_invite(
        self, code: str, channel: str, channel_id: str, now: float | None = None
    ) -> Binding: ...
    def lookup(self, channel: str, channel_id: str) -> Binding | None: ...
    def unlink(self, channel: str, channel_id: str) -> bool: ...


class InviteError(Exception):
    """Raised when an invite code is unknown, expired, or already used."""


class AlreadyLinkedError(Exception):
    """Raised when a channel id is already bound to a household."""


def _new_code() -> str:
    """6-char invite code, unambiguous alphabet, URL-safe enough for SMS."""
    return "".join(secrets.choice("ABCDEFGHJKMNPQRSTUVWXYZ23456789") for _ in range(6))


class InMemoryBindingStore:
    """Thread-unsafe by design; one process per household family in tests."""

    def __init__(self, ttl_seconds: int = DEFAULT_INVITE_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._invites: dict[str, InviteCode] = {}
        self._bindings: dict[tuple[str, str], Binding] = {}

    def issue_invite(self, household_id: str, now: float | None = None) -> InviteCode:
        now_f = now if now is not None else time.time()
        # Re-issue rather than collide: codes are long enough that collision is
        # astronomically rare, but a retry path costs nothing.
        for _ in range(5):
            code = _new_code()
            if code not in self._invites:
                invite = InviteCode(
                    code=code, household_id=household_id, expires_at=now_f + self._ttl
                )
                self._invites[code] = invite
                return invite
        raise RuntimeError("could not generate a unique invite code")

    def consume_invite(
        self, code: str, channel: str, channel_id: str, now: float | None = None
    ) -> Binding:
        now_f = now if now is not None else time.time()
        invite = self._invites.get(code)
        if invite is None or invite.consumed or invite.expires_at <= now_f:
            raise InviteError("invite code invalid or expired")
        existing = self._bindings.get((channel, channel_id))
        if existing is not None:
            raise AlreadyLinkedError("channel already linked")
        self._invites[code] = InviteCode(
            code=invite.code,
            household_id=invite.household_id,
            expires_at=invite.expires_at,
            consumed=True,
        )
        binding = Binding(
            channel=channel,
            channel_id=channel_id,
            household_id=invite.household_id,
            linked_at=now_f,
        )
        self._bindings[(channel, channel_id)] = binding
        return binding

    def lookup(self, channel: str, channel_id: str) -> Binding | None:
        return self._bindings.get((channel, channel_id))

    def unlink(self, channel: str, channel_id: str) -> bool:
        return self._bindings.pop((channel, channel_id), None) is not None


class DynamoBindingStore:
    """DynamoDB-backed binding store. Uses two PK patterns per doc 06.

    Items:
    - BINDING#<channel>#<channel_id> -> {household_id, linked_at}
    - INVITE#<code> -> {household_id, expires_at, consumed}
    """

    def __init__(
        self, client: Any, table_name: str, ttl_seconds: int = DEFAULT_INVITE_TTL_SECONDS
    ) -> None:
        self._client = client
        self._table = table_name
        self._ttl = ttl_seconds

    def issue_invite(self, household_id: str, now: float | None = None) -> InviteCode:
        now_f = now if now is not None else time.time()
        code = _new_code()
        self._client.put_item(
            TableName=self._table,
            Item={
                "pk": {"S": f"INVITE#{code}"},
                "sk": {"S": "META"},
                "household_id": {"S": household_id},
                "expires_at": {"N": str(int(now_f + self._ttl))},
                "consumed": {"BOOL": False},
            },
            ConditionExpression="attribute_not_exists(pk)",
        )
        return InviteCode(code=code, household_id=household_id, expires_at=now_f + self._ttl)

    def consume_invite(
        self, code: str, channel: str, channel_id: str, now: float | None = None
    ) -> Binding:
        now_f = now if now is not None else time.time()
        resp = self._client.update_item(
            TableName=self._table,
            Key={"pk": {"S": f"INVITE#{code}"}, "sk": {"S": "META"}},
            UpdateExpression=("SET consumed = :true"),
            ConditionExpression=(
                "attribute_exists(pk) AND consumed = :false AND expires_at > :now"
            ),
            ExpressionAttributeValues={
                ":true": {"BOOL": True},
                ":false": {"BOOL": False},
                ":now": {"N": str(int(now_f))},
            },
            ReturnValues="ALL_NEW",
        )
        attrs = resp.get("Attributes", {})
        household_id = attrs.get("household_id", {}).get("S", "")
        if not household_id:
            raise InviteError("invite consumed but no household returned")
        # Conditional link write to enforce single-binding.
        self._client.put_item(
            TableName=self._table,
            Item={
                "pk": {"S": f"BINDING#{channel}#{channel_id}"},
                "sk": {"S": "META"},
                "household_id": {"S": household_id},
                "linked_at": {"N": str(int(now_f))},
            },
            ConditionExpression="attribute_not_exists(pk)",
        )
        return Binding(
            channel=channel, channel_id=channel_id, household_id=household_id, linked_at=now_f
        )

    def lookup(self, channel: str, channel_id: str) -> Binding | None:
        resp = self._client.get_item(
            TableName=self._table,
            Key={"pk": {"S": f"BINDING#{channel}#{channel_id}"}, "sk": {"S": "META"}},
        )
        item = resp.get("Item")
        if not item:
            return None
        return Binding(
            channel=channel,
            channel_id=channel_id,
            household_id=item.get("household_id", {}).get("S", ""),
            linked_at=float(item.get("linked_at", {}).get("N", "0")),
        )

    def unlink(self, channel: str, channel_id: str) -> bool:
        resp = self._client.delete_item(
            TableName=self._table,
            Key={"pk": {"S": f"BINDING#{channel}#{channel_id}"}, "sk": {"S": "META"}},
            ReturnValues="ALL_OLD",
        )
        return bool(resp.get("Attributes"))


def verify_sender(store: BindingStore, channel: str, channel_id: str) -> Binding:
    """Raise UnlinkedSenderError if the sender is not bound to a household."""
    binding = store.lookup(channel, channel_id)
    if binding is None:
        raise UnlinkedSenderError("sender not linked to any household")
    return binding


class UnlinkedSenderError(Exception):
    """Raised by the intake path when a channel id has no household binding."""
