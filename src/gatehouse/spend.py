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
import time
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
class HourlyBreaker:
    """Rolling cap on model calls per hour, above every per-case budget.

    The per-case meter cannot bound spend ACROSS cases: a fresh meter is
    built for every investigation, so a flood of forwards is a flood of
    independent budgets with no ceiling over them. Charter principle 7 asks
    for caps per hour and per investigation; this is the per-hour half.

    Scope honesty: this is process-level state. Under Lambda that is one warm
    container, so a fan-out across many cold containers can still exceed the
    cap in aggregate. A true cross-invocation ceiling needs a shared counter
    (a DynamoDB atomic add on an hour-bucketed key). Until that lands, this
    bounds the runaway that actually happens in practice, which is one hot
    container looping, and it never under-reports: refusing early is the safe
    direction for a spend guard.
    """

    max_calls_per_hour: int
    _calls: list[float] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def _prune(self, now: float) -> None:
        cutoff = now - 3600.0
        self._calls = [t for t in self._calls if t > cutoff]

    def allow(self, now: float | None = None) -> bool:
        """Breaker check BEFORE a call is made."""
        moment = time.time() if now is None else now
        with self._lock:
            self._prune(moment)
            return len(self._calls) < self.max_calls_per_hour

    def record(self, now: float | None = None) -> None:
        """Account one call against the hour window."""
        moment = time.time() if now is None else now
        with self._lock:
            self._prune(moment)
            self._calls.append(moment)

    @property
    def calls_this_hour(self) -> int:
        with self._lock:
            self._prune(time.time())
            return len(self._calls)


@dataclass
class SpendMeter:
    """Accumulates CallRecords for one case (or any scope you choose).

    An optional HourlyBreaker is consulted alongside the per-case budget, so
    a single meter cannot authorise a call the hour has already spent.
    """

    max_usd: float
    max_calls: int
    records: list[CallRecord] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    hourly: HourlyBreaker | None = None

    @staticmethod
    def estimate_usd(model_id: str, input_tokens: int, output_tokens: int) -> float:
        rate_in, rate_out = SpendMeter._rates_for(model_id)
        return round((input_tokens * rate_in + output_tokens * rate_out) / 1_000_000, 6)

    @staticmethod
    def _rates_for(model_id: str) -> tuple[float, float]:
        """Exact match first; regional inference-profile prefixes (apac., eu.,
        us.) resolve to the same underlying model's price. An unknown id still
        gets the most expensive known rate rather than zero (fail conservative).
        """
        rates = MODEL_RATES_USD_PER_MTOK.get(model_id)
        if rates is not None:
            return rates
        _, _, rest = model_id.partition(".")
        if rest:
            stripped = MODEL_RATES_USD_PER_MTOK.get(rest)
            if stripped is not None:
                return stripped
        return _FALLBACK_RATE

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
        # The hour is charged wherever the case is charged; a call accounted
        # to one budget and not the other is a hole in the ceiling.
        if self.hourly is not None:
            self.hourly.record()
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
        """Breaker check BEFORE a call is made.

        Both ceilings must agree. The hour cap is checked too, so refusing is
        the union of the two budgets rather than the per-case one alone.
        """
        with self._lock:
            under_calls = len(self.records) < self.max_calls
            under_budget = sum(r.est_usd for r in self.records) < self.max_usd
        if not (under_calls and under_budget):
            return False
        return self.hourly.allow() if self.hourly is not None else True


class BudgetExceeded(Exception):
    """Raised by the guard when the breaker refuses a call."""


_HOURLY_BREAKER: HourlyBreaker | None = None
_BREAKER_LOCK = threading.Lock()


def get_hourly_breaker(max_calls_per_hour: int) -> HourlyBreaker:
    """Process-wide breaker singleton.

    Shared deliberately: a per-caller breaker would be per-case again, which
    is the gap this exists to close. The cap is read once per process, so
    changing it takes a redeploy, same as every other breaker constant.
    """
    global _HOURLY_BREAKER
    with _BREAKER_LOCK:
        if _HOURLY_BREAKER is None:
            _HOURLY_BREAKER = HourlyBreaker(max_calls_per_hour=max_calls_per_hour)
        return _HOURLY_BREAKER


def reset_hourly_breaker() -> None:
    """Drop the singleton. Tests only: process state must not leak between them."""
    global _HOURLY_BREAKER
    with _BREAKER_LOCK:
        _HOURLY_BREAKER = None
