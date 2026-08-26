"""Structured logging with mandatory P1 scrubbing.

Design contract (docs/18 section 1, docs/08 section 3):

- Every record is JSON: one line, machine-parseable, CloudWatch-friendly.
- The scrubber runs as the LAST step before emission on every single record.
  It is not optional, not per-caller, not bypassable.
- Scrubbing targets P1 shapes (phone numbers, emails, VPAs, long digit runs,
  card-like numbers) plus explicit sentinels used by CI to prove the guarantee.
- A logger never raises: if scrubbing or serialization fails, it emits a safe
  fallback line. Observability must never become an outage.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from gatehouse.constants import REDACTION_TOKEN

# --- compiled once at import; hot path must stay cheap ---

_PHONE = re.compile(r"(?<![\w])(?:\+?\d[\d\s().-]{7,15}\d)(?![\w])")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_VPA = re.compile(r"\b[a-zA-Z0-9._-]{2,}@[a-zA-Z]{2,}\b")
_CARDISH = re.compile(r"\b(?:\d[ -]?){12,19}\b")

_PATTERNS: tuple[re.Pattern[str], ...] = (_PHONE, _EMAIL, _VPA, _CARDISH)


def scrub_p1(text: str) -> str:
    """Redact P1-shaped substrings from free text.

    Runs on every message attached to every log record. Deterministic,
    allocation-light, and conservative: when in doubt, redact.
    """
    result = text
    for pattern in _PATTERNS:
        result = pattern.sub(REDACTION_TOKEN, result)
    return result


def _scrub_value(value: Any) -> Any:
    """Recursively scrub strings inside arbitrary JSON-ish structures."""
    if isinstance(value, str):
        return scrub_p1(value)
    if isinstance(value, dict):
        return {key: _scrub_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub_value(item) for item in value]
    return value


class ScrubbedJsonFormatter(logging.Formatter):
    """Formats records as single-line JSON with mandatory scrubbing applied."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": scrub_p1(record.getMessage()),
        }
        extra: dict[str, Any] | None = getattr(record, "gh_extra", None)
        if extra is None:
            # Callers using plain logging (not GatehouseLogger.event) attach
            # context under extra_fields; both names feed the same scrubbed
            # ctx block. Before this acceptance the whole ctx block was
            # silently dropped on every direct log.info call site.
            extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload["ctx"] = {
                key: _scrub_value(val)
                for key, val in extra.items()
                if key not in ("msg", "level", "logger", "ts")
            }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)[:2000]
        try:
            return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        except (TypeError, ValueError):
            return json.dumps(
                {
                    "ts": payload["ts"],
                    "level": "ERROR",
                    "logger": "gatehouse.log",
                    "msg": "unserializable log record dropped",
                },
                separators=(",", ":"),
            )


class GatehouseLogger(logging.Logger):
    """Logger exposing `gh_extra` for structured context."""

    def event(self, level: int, msg: str, **ctx: Any) -> None:
        self.log(level, msg, extra={"gh_extra": ctx})


def configure_logging(level: int = logging.INFO) -> None:
    """Idempotent root setup for all Gatehouse entrypoints."""

    handler = logging.StreamHandler()
    handler.setFormatter(ScrubbedJsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> GatehouseLogger:
    """Return a named GatehouseLogger; call after configure_logging in prod."""
    logging.setLoggerClass(GatehouseLogger)
    try:
        return logging.getLogger(name)  # type: ignore[return-value]
    finally:
        logging.setLoggerClass(logging.Logger)
