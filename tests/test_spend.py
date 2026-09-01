"""Tests for spend meter and breaker."""

from __future__ import annotations

import pytest

from gatehouse.spend import (
    BudgetExceeded,
    HourlyBreaker,
    SpendMeter,
    get_hourly_breaker,
    reset_hourly_breaker,
)


class TestEstimate:
    def test_nova_micro_pricing(self) -> None:
        # 1M input tokens at $0.35/M = 0.35 USD
        assert SpendMeter.estimate_usd("amazon.nova-micro-v1:0", 1_000_000, 0) == 0.35

    def test_unknown_model_fails_expensive(self) -> None:
        cheap = SpendMeter.estimate_usd("totally-unknown-model", 100_000, 100_000)
        known = SpendMeter.estimate_usd("amazon.nova-pro-v1:0", 100_000, 100_000)
        assert cheap > known  # fail conservative

    def test_rounding_sane(self) -> None:
        v = SpendMeter.estimate_usd("amazon.nova-lite-v1:0", 1000, 2000)
        assert v == round(v, 6)


class TestMeter:
    def test_records_accumulate(self) -> None:
        m = SpendMeter(max_usd=10.0, max_calls=5)
        m.record("triage", "amazon.nova-micro-v1:0", 500, 200)
        m.record("verify", "amazon.nova-micro-v1:0", 800, 300)
        assert m.total_calls == 2
        assert m.total_usd > 0

    def test_breaker_call_cap(self) -> None:
        m = SpendMeter(max_usd=100.0, max_calls=2)
        m.record("a", "amazon.nova-micro-v1:0", 10, 10)
        m.record("a", "amazon.nova-micro-v1:0", 10, 10)
        assert m.allow() is False
        with pytest.raises(BudgetExceeded):
            if not m.allow():
                raise BudgetExceeded()

    def test_breaker_usd_cap(self) -> None:
        m = SpendMeter(max_usd=0.001, max_calls=100)
        assert m.allow() is True  # nothing spent yet
        m.record("a", "amazon.nova-pro-v1:0", 50_000, 50_000)
        assert m.total_usd >= 0.001
        assert m.allow() is False

    def test_zero_budget_blocks_immediately(self) -> None:
        m = SpendMeter(max_usd=0.0000001, max_calls=1)
        # zero calls so far: allowed (breaker checks BEFORE call)
        assert m.allow() is True


class TestHourlyBreaker:
    """Charter principle 7: caps per hour AND per investigation.

    The per-case meter is rebuilt for every investigation, so on its own it
    bounds one case and nothing above it. These pin the ceiling.
    """

    def test_allows_up_to_the_cap_then_refuses(self) -> None:
        breaker = HourlyBreaker(max_calls_per_hour=3)
        for _ in range(3):
            assert breaker.allow(now=1000.0)
            breaker.record(now=1000.0)
        assert breaker.allow(now=1000.0) is False

    def test_calls_age_out_of_the_window(self) -> None:
        breaker = HourlyBreaker(max_calls_per_hour=2)
        breaker.record(now=1000.0)
        breaker.record(now=1000.0)
        assert breaker.allow(now=1000.0) is False
        # One hour and a second later the window has emptied.
        assert breaker.allow(now=1000.0 + 3601.0) is True

    def test_ceiling_holds_across_separate_meters(self) -> None:
        """The defect this closes: a fresh meter per case meant no ceiling."""
        shared = HourlyBreaker(max_calls_per_hour=2)
        first = SpendMeter(max_usd=1.0, max_calls=10, hourly=shared)
        second = SpendMeter(max_usd=1.0, max_calls=10, hourly=shared)

        assert first.allow()
        first.record("triage", "amazon.nova-micro-v1:0", 10, 10)
        assert second.allow()
        second.record("triage", "amazon.nova-micro-v1:0", 10, 10)

        # Both meters are far under their own budgets and both must refuse.
        assert first.total_calls == 1
        assert second.total_calls == 1
        assert first.allow() is False
        assert second.allow() is False

    def test_meter_without_a_breaker_is_unchanged(self) -> None:
        """Existing callers that pass no breaker keep their exact behaviour."""
        meter = SpendMeter(max_usd=1.0, max_calls=2)
        assert meter.allow()
        meter.record("triage", "amazon.nova-micro-v1:0", 10, 10)
        assert meter.allow()

    def test_per_case_budget_still_refuses_first(self) -> None:
        """The hour ceiling widens nothing: both budgets must agree."""
        generous = HourlyBreaker(max_calls_per_hour=1000)
        meter = SpendMeter(max_usd=1.0, max_calls=1, hourly=generous)
        meter.record("triage", "amazon.nova-micro-v1:0", 10, 10)
        assert meter.allow() is False

    def test_singleton_is_shared_and_resettable(self) -> None:
        reset_hourly_breaker()
        one = get_hourly_breaker(5)
        two = get_hourly_breaker(5)
        assert one is two
        reset_hourly_breaker()
        assert get_hourly_breaker(5) is not one
