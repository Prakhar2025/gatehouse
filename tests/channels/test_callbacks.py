"""Tests for Telegram callback resolution: expiry, idempotency, validation."""

from __future__ import annotations

from typing import Any

import pytest

from gatehouse.channels.callbacks import (
    ALLOWED_ACTIONS,
    CALLBACK_TTL_SECONDS,
    CallbackError,
    parse_callback_query,
    resolve_callback,
)


class FakeCaseStore:
    """In-memory double mirroring the case-store contract."""

    def __init__(self, cases: dict[str, dict[str, Any]] | None = None) -> None:
        self.cases = cases or {}
        self.decisions: list[tuple[str, str, str, float]] = []

    def get(self, case_id: str) -> dict[str, Any] | None:
        return self.cases.get(case_id)

    def record_decision(self, case_id: str, actor: str, action: str, decided_at: float) -> None:
        self.decisions.append((case_id, actor, action, decided_at))
        self.cases[case_id]["decided_at"] = decided_at
        self.cases[case_id]["decision"] = action


def _payload(case_id: str = "case-1", action: str = "BLOCK") -> dict[str, Any]:
    return {
        "callback_query": {
            "id": "cbq-1",
            "from": {"id": 777},
            "data": f"{case_id}|{action}",
        }
    }


class TestParse:
    def test_valid_parse(self) -> None:
        q = parse_callback_query(_payload())
        assert q.case_id == "case-1" and q.action == "BLOCK" and q.chat_id == 777

    def test_not_a_callback_raises(self) -> None:
        with pytest.raises(CallbackError):
            parse_callback_query({"message": {}})

    def test_unknown_action_raises(self) -> None:
        with pytest.raises(CallbackError):
            parse_callback_query(_payload(action="NUKE"))

    def test_allowed_actions_fixed(self) -> None:
        assert set(ALLOWED_ACTIONS) == {"BLOCK", "ALLOW", "ESCALATE_HUMAN"}

    def test_missing_separator_raises(self) -> None:
        with pytest.raises(CallbackError):
            parse_callback_query(
                {"callback_query": {"id": "x", "from": {"id": 1}, "data": "justacase"}}
            )


class TestResolve:
    def _store(self) -> FakeCaseStore:
        return FakeCaseStore({"case-1": {"created_at": 0.0}})

    def test_applied_records_decision(self) -> None:
        store = self._store()
        outcome, text = resolve_callback(parse_callback_query(_payload()), store, now=100.0)
        assert outcome == "applied"
        assert "console" not in text.lower()
        assert store.decisions[0][2] == "BLOCK"

    def test_expired_after_48h_gets_console_pointer(self) -> None:
        store = self._store()
        q = parse_callback_query(_payload())
        outcome, text = resolve_callback(q, store, now=CALLBACK_TTL_SECONDS + 1)
        assert outcome == "expired"
        assert "console" in text.lower()

    def test_within_48h_still_applies(self) -> None:
        store = self._store()
        outcome, _ = resolve_callback(
            parse_callback_query(_payload()), store, now=CALLBACK_TTL_SECONDS - 60
        )
        assert outcome == "applied"

    def test_duplicate_press_is_idempotent(self) -> None:
        store = self._store()
        q = parse_callback_query(_payload())
        resolve_callback(q, store, now=100.0)
        outcome, _ = resolve_callback(q, store, now=101.0)
        assert outcome == "duplicate"
        # First decision stands; second press added no new history.
        assert len(store.decisions) == 1

    def test_already_decided_before_expiry_is_duplicate(self) -> None:
        store = FakeCaseStore({"case-1": {"created_at": 0.0, "decided_at": 50.0}})
        outcome, _ = resolve_callback(parse_callback_query(_payload()), store, now=60.0)
        assert outcome == "duplicate"

    def test_missing_case_refuses(self) -> None:
        outcome, text = resolve_callback(
            parse_callback_query(_payload(case_id="ghost")),
            FakeCaseStore(),
            now=10.0,
        )
        assert outcome == "missing_case"
        assert "console" in text.lower()

    def test_actor_tagged_with_telegram_id(self) -> None:
        store = self._store()
        resolve_callback(parse_callback_query(_payload()), store, now=5.0)
        assert store.decisions[0][1] == "tg:777"
