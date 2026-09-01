"""Tests for the engage agent: flags, firewall, stop conditions. Mock-model only."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

import gatehouse.agents.engage as engage
from gatehouse.agents.engage import (
    OUTCOME_BENIGN_EXIT,
    OUTCOME_FIREWALL_TRIP,
    OUTCOME_GOAL_ACHIEVED,
    OUTCOME_MONEY_TEST,
    OUTCOME_NOT_ENABLED,
    OUTCOME_THREAT_DETECTED,
    OutboundFirewall,
    run_engagement,
)

pytest.importorskip("strands")

from gatehouse.agents.mock_model import MockModel


class FakeChannel:
    """Scripted inbound queue; records everything the persona sends."""

    def __init__(self, replies: list[str | None]) -> None:
        self._replies = list(replies)
        self.sent: list[str] = []

    def deliver(self, to_contact: str, text: str) -> bool:
        self.sent.append(text)
        return True

    def receive(self, contact: str) -> str | None:
        return self._replies.pop(0) if self._replies else None


def _model(
    reply_text: str = "What documents did they ask for?",
    *,
    goal_achieved: bool = False,
    appears_benign: bool = False,
    intent: float = 0.8,
) -> MockModel:
    return MockModel(
        tool_payload={
            "reply_text": reply_text,
            "scammer_intent_confidence": intent,
            "goal_achieved": goal_achieved,
            "appears_benign": appears_benign,
        }
    )


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


class TestFlagsAndLimits:
    def test_not_opted_in_short_circuits(self) -> None:
        result = _run(
            run_engagement(
                "case-1",
                "@scammer",
                "confirm intent",
                FakeChannel(["hi"]),
                household_opt_in=False,
            )
        )
        assert result.outcome == OUTCOME_NOT_ENABLED
        assert result.turns_used == 0

    def test_turn_limit_six(self) -> None:
        channel = FakeChannel(["msg"] * 20)
        result = _run(
            run_engagement(
                "case-1",
                "@scammer",
                "confirm intent",
                channel,
                model=_model(),
                max_turns=6,
            )
        )
        assert result.outcome == "TURN_LIMIT"
        assert result.turns_used == 6
        # opener + 6 replies, one inbound consumed per turn
        assert len(channel.sent) == 7

    def test_goal_achieved_stops_early(self) -> None:
        result = _run(
            run_engagement(
                "case-1",
                "@scammer",
                "get the UPI id",
                FakeChannel([f"reply {i}" for i in range(10)]),
                model=_model(goal_achieved=True),
            )
        )
        assert result.outcome == OUTCOME_GOAL_ACHIEVED
        assert result.turns_used == 1


class TestInboundThreats:
    def test_threat_stops_immediately(self) -> None:
        result = _run(
            run_engagement(
                "case-1",
                "@scammer",
                "confirm intent",
                FakeChannel(["I know where you live"]),
                model=_model(),
            )
        )
        assert result.outcome == OUTCOME_THREAT_DETECTED
        # blocked turn persists no scammer text
        assert all(t.text == "" for t in result.transcript if t.direction == "IN")

    def test_money_move_request_stops(self) -> None:
        result = _run(
            run_engagement(
                "case-1",
                "@scammer",
                "confirm intent",
                FakeChannel(["just send money now to finish"]),
                model=_model(),
            )
        )
        assert result.outcome == OUTCOME_MONEY_TEST

    def test_no_response_when_queue_empty(self) -> None:
        result = _run(run_engagement("case-1", "@scammer", "g", FakeChannel([]), model=_model()))
        assert result.outcome == "NO_RESPONSE"


class TestOutboundFirewall:
    def test_canary_leak_blocked(self) -> None:
        fw = OutboundFirewall(canary="ghc_abc123")
        allowed, reason = fw.check("my audit marker is ghc_abc123 ok")
        assert not allowed and reason == "CANARY_LEAK"

    @pytest.mark.parametrize(
        ("text", "reason"),
        [
            ("your otp is 482913 sir", "DIGIT_RUN"),
            ("pay to fraud@ybl", "UPI_HANDLE"),
            ("mail me at a@b.com", "EMAIL_ADDRESS"),
            ("come to house no 12", "ADDRESS_SHAPE"),
            ("share member PII now", "MEMBER_PII"),
        ],
    )
    def test_pii_shapes_blocked(self, text: str, reason: str) -> None:
        fw = OutboundFirewall(canary="ghc_x", blocked_terms=["member pii"])
        allowed, got = fw.check(text)
        assert not allowed and got == reason

    def test_normal_persona_reply_allowed(self) -> None:
        fw = OutboundFirewall(canary="ghc_x")
        allowed, reason = fw.check("Ok auntie sent details, what happens after that?")
        assert allowed and reason == "OK"

    def test_firewall_trip_ends_engagement(self) -> None:
        result = _run(
            run_engagement(
                "case-1",
                "@scammer",
                "g",
                FakeChannel(["r1", "r2"]),
                model=_model(reply_text="the otp is 998877"),
            )
        )
        assert result.outcome == OUTCOME_FIREWALL_TRIP


class TestDegradedPaths:
    def test_budget_refused(self) -> None:
        class FullMeter:
            def allow(self) -> bool:
                return False

            def record(self, *a: Any, **k: Any) -> None:
                return None

        result = _run(
            run_engagement(
                "case-1",
                "@s",
                "g",
                FakeChannel(["x"]),
                meter=FullMeter(),  # type: ignore[arg-type]
            )
        )
        assert result.outcome == "BUDGET_REFUSED"
        assert "ENGAGE_BUDGET_REFUSED" in result.degraded_flags

    def test_model_error_is_inconclusive_not_crash(self) -> None:
        class BoomModel:
            pass

        result = _run(
            run_engagement("case-1", "@s", "g", FakeChannel(["inbound"]), model=BoomModel())
        )
        assert result.outcome == "INCONCLUSIVE"
        assert any(f.startswith("ENGAGE_MODEL_FALLBACK") for f in result.degraded_flags)

    def test_benign_exit(self) -> None:
        result = _run(
            run_engagement(
                "case-1",
                "@s",
                "g",
                FakeChannel(["hello?"]),
                model=_model(appears_benign=True, intent=0.1),
            )
        )
        assert result.outcome == OUTCOME_BENIGN_EXIT
        assert result.intent_confidence == 0.1


class _NullChannel:
    """Channel double: never touched when consent is refused up front."""

    def deliver(self, contact: str, text: str) -> bool:
        return True

    def receive(self, contact: str) -> str | None:
        return None


def test_member_consent_refused_before_any_model_call() -> None:
    """Per-member consent (doc 19): even with the household opted in, a case
    forwarded by a member who has not consented to engagement must refuse
    before the model is touched."""

    class _NoCallModel:
        async def structured_output(self, *a: Any, **k: Any) -> None:  # pragma: no cover
            raise AssertionError("model must not be called without member consent")

    result = _run(
        engage.run_engagement(
            "case-consent",
            "+911234567890",
            "confirm scam",
            _NullChannel(),
            household_opt_in=True,
            member_consent=False,
            model=_NoCallModel(),
        )
    )
    assert result.outcome == engage.OUTCOME_NOT_ENABLED
    assert result.reason_code == "member_not_consented"
    assert result.turns_used == 0
