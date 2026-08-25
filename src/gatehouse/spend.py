"""Spend governance: the meter and the breaker (charter section 8).

The meter records every model call's token counts and estimated cost. The
breaker refuses calls once any budget is exceeded, converting cost overrun into
an explicit degraded mode instead of a surprise bill.

Design notes:
- Costs are configured per model id in one table; unknown models get the
  most expensive known rate rather than zero (fail conservative).
- Thread safety: P2 runs single-threaded per case, but a threading.Lock keeps
  this correct under AgentCore concurrency later without interface changes.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

# USD per 1M tokens, input/output, from the Aug 2026 pricing review.
MODEL_RATES_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "amazon.nova-micro-v1:0": (0.35, 1.40),
    "amazon.nova-lite-v1:0": (0.60, 2.40),
    "amazon.nova-pro-v1:0": (0.80, 3.20),
    "zai.glm-4.7-flash": (0.10, 0.70),
    "us.meta.llama3-3-70b-instruct-v1:0": (0.72, 0.72),
    "openai.gpt-oss-120b-1:0": (0.15, 0.60),
}
_FALLBACK_RATE: tuple[float, float] = (5.00, 25.00)  # assume expensive when unknown


@dataclass(frozen=True)
class CallRecord:
    """One accounted model call."""

    agent: str
    model_id: str
    input_tokens: int
    output_tokens: int
    est_usd: float


@dataclass
class SpendMeter:
    """Accumulates CallRecords for one case (or any scope you choose)."""

    max_usd: float
    max_calls: int
    records: list[CallRecord] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @staticmethod
    def estimate_usd(model_id: str, input_tokens: int, output_tokens: int) -> float:
        rate_in, rate_out = MODEL_RATES_USD_PER_MTOK.get(model_id, _FALLBACK_RATE)
        return round((input_tokens * rate_in + output_tokens * rate_out) / 1_000_000, 6)

    def record(
        self, agent: str, model_id: str, input_tokens: int, output_tokens: int
    ) -> CallRecord:
        rec = CallRecord(
            agent=agent,
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            est_usd=self.estimate_usd(model_id, input_tokens, output_tokens),
        )
        with self._lock:
            self.records.append(rec)
        return rec

    @property
    def total_usd(self) -> float:
        with self._lock:
            return round(sum(r.est_usd for r in self.records), 6)

    @property
    def total_calls(self) -> int:
        with self._lock:
            return len(self.records)

    def allow(self) -> bool:
        """Breaker check BEFORE a call is made."""
        with self._lock:
            under_calls = len(self.records) < self.max_calls
            under_budget = sum(r.est_usd for r in self.records) < self.max_usd
            return under_calls and under_budget


class BudgetExceeded(Exception):
    """Raised by the guard when the breaker refuses a call."""
