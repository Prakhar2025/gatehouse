"""Case traces: one scrubbed JSON line that reconstructs any case end to end.

P4 observability contract (doc 11): traces reconstruct any case. One
CaseTrace per investigation collects an ordered span per pipeline stage
(fence, triage, verify, graph, guardian) plus free-form notes, and emits a
single ``case_trace`` log line at completion. Spans carry stage name,
status, duration, and error CLASS only: messages can carry member data,
trace fields must not need to.

Same law as the logging layer applies here: tracing never raises. Any
failure inside the recorder degrades to fewer fields, never to a broken
investigation.
"""

from __future__ import annotations

import contextlib
import time
from types import TracebackType
from typing import Any

from gatehouse.logging_utils import get_logger

log = get_logger("gatehouse.trace")


class Span:
    """One timed stage inside a case trace."""

    __slots__ = ("_started", "error", "stage", "status")

    def __init__(self, stage: str) -> None:
        self.stage = stage
        self.status = "ok"
        self.error: str | None = None
        self._started = time.perf_counter()

    @property
    def duration_ms(self) -> float:
        """Milliseconds elapsed since the span started (read at emit time)."""
        return round((time.perf_counter() - self._started) * 1000, 2)

    def snapshot(self) -> dict[str, Any]:
        """Plain dict for the emitted payload."""
        return {
            "stage": self.stage,
            "status": self.status,
            "ms": self.duration_ms,
            **({"err": self.error} if self.error else {}),
        }


class _StageContext:
    """Context manager marking one stage; captures failure as a class name."""

    def __init__(self, trace: CaseTrace, stage: str) -> None:
        self._span = Span(stage)
        self._trace = trace

    def __enter__(self) -> Span:
        self._trace.spans.append(self._span)
        return self._span

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            self._span.status = "failed"
            self._span.error = exc_type.__name__


class CaseTrace:
    """Ordered stage spans plus notes for exactly one case."""

    def __init__(self, case_id: str, channel: str = "") -> None:
        self.case_id = case_id
        self.channel = channel
        self.spans: list[Span] = []
        self.notes: dict[str, Any] = {}
        self._opened = time.perf_counter()

    def stage(self, name: str) -> _StageContext:
        """Open a timed span; use as ``with trace.stage("triage"):``."""
        return _StageContext(self, name)

    def note(self, key: str, value: Any) -> None:
        """Attach one reconstruction fact (verdict, spend, flags)."""
        self.notes[key] = value

    @property
    def total_ms(self) -> float:
        """Wall time from trace open to emit."""
        return round((time.perf_counter() - self._opened) * 1000, 2)

    def emit(self, status: str = "ok") -> None:
        """Log the whole trace as one line. Never raises."""
        payload: dict[str, Any] = {
            "case_id": self.case_id,
            "status": status,
            "total_ms": self.total_ms,
            "stages": [span.snapshot() for span in self.spans],
        }
        if self.channel:
            payload["channel"] = self.channel
        if self.notes:
            payload["facts"] = self.notes
        # Observability must never become an outage: a formatter or sink
        # failure drops this one line and nothing else.
        with contextlib.suppress(Exception):
            log.info("case_trace", extra={"extra_fields": payload})


def noop_trace(case_id: str) -> CaseTrace:
    """A trace nobody reads, for callers that did not open one."""
    return CaseTrace(case_id)
