"""Tests for the EventBridge publisher: batching, signing, honest failures."""

from __future__ import annotations

import json
from typing import Any

from gatehouse.channels.bus import BATCH_LIMIT, SOURCE, EventBridgePublisher
from gatehouse.channels.events import GatewayEvent, build_envelope, verify_event


class FakeEventBridge:
    """Mirrors put_events semantics: per-entry success/failure."""

    def __init__(self, fail_indices: set[int] | None = None) -> None:
        self.calls: list[list[dict[str, Any]]] = []
        self._fail = fail_indices or set()
        self._seq = 0

    def put_events(self, Entries: list[dict[str, Any]]) -> dict[str, Any]:
        self.calls.append(Entries)
        out = []
        for _entry in Entries:
            if self._seq in self._fail:
                out.append({"ErrorCode": "InternalFailure", "ErrorMessage": "boom"})
            else:
                out.append({"EventId": f"evt-{self._seq}"})
            self._seq += 1
        return {"Entries": out}


def _envelope(n: int = 1) -> list[dict[str, Any]]:
    return [
        build_envelope(
            GatewayEvent(
                channel="telegram",
                household_id=f"fam-{i}",
                sender_name="T",
                text=f"msg {i}",
                is_forward=True,
                received_at=1000.0,
            )
        )
        for i in range(n)
    ]


def test_single_envelope_publishes_signed_detail() -> None:
    client = FakeEventBridge()
    publisher = EventBridgePublisher(client, signing_key="k")
    result = publisher.publish(_envelope(1))
    assert result.published == 1 and result.failed == 0

    entries = client.calls[0]
    assert entries[0]["Source"] == SOURCE
    detail = json.loads(entries[0]["Detail"])
    # Consumer-side verification round trip: signature must validate.
    assert verify_event(detail, detail.pop("signature"), "k") is True


def test_batching_at_service_limit() -> None:
    client = FakeEventBridge()
    publisher = EventBridgePublisher(client, signing_key="k")
    result = publisher.publish(_envelope(BATCH_LIMIT * 2 + 3))
    assert result.published == BATCH_LIMIT * 2 + 3
    assert [len(c) for c in client.calls] == [BATCH_LIMIT, BATCH_LIMIT, 3]


def test_failed_entries_counted_honestly() -> None:
    client = FakeEventBridge(fail_indices={1})  # second event fails
    publisher = EventBridgePublisher(client, signing_key="k")
    result = publisher.publish(_envelope(4))
    assert result.published == 3 and result.failed == 1


def test_event_id_rides_as_resource_arm() -> None:
    client = FakeEventBridge()
    publisher = EventBridgePublisher(client, signing_key="k")
    (env,) = envs = _envelope(1)
    publisher.publish(envs)
    assert client.calls[0][0]["Resources"] == [env["event_id"]]
