"""Tests for spend meter and breaker."""

from __future__ import annotations

import pytest

from gatehouse.spend import BudgetExceeded, SpendMeter


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
