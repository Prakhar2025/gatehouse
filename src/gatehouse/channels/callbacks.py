"""Telegram callback queries: verdict-card button presses (doc 05 section 2).

Guardian cards carry inline buttons; this module owns their lifecycle:
- parse_callback_query extracts one validated callback from an update.
- resolve_callback applies the guardian decision to a case.
- Buttons expire after 48 hours (doc 05 section 7 test matrix): expired
  presses get a graceful expiry message while the case itself stays
  resolvable in the console. Expiry is data-driven via decided_at/created_at
  on the case record, never assumed from transport timing.

Store contract: any object exposing get(case_id) -> dict | None and
record_decision(case_id, actor, action, decided_at). The DynamoDB-backed
store arrives with the case persistence wiring; tests double it here.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol

CALLBACK_TTL_SECONDS = 48 * 3600
ALLOWED_ACTIONS = ("BLOCK", "ALLOW", "ESCALATE_HUMAN")

_EXPIRED_TEXT = (
    "This card has expired. Open the Gatehouse console to resolve the case: "
    "your decision still counts there."
)
_DECIDED_TEXT = "Recorded. Thank you."


class CallbackError(Exception):
    """Raised for callback payloads that must not be processed."""


class CaseCallbackStore(Protocol):
    def get(self, case_id: str) -> dict[str, Any] | None: ...

    def record_decision(self, case_id: str, actor: str, action: str, decided_at: float) -> None: ...


@dataclass(frozen=True)
class CallbackQuery:
    """One validated button press."""

    callback_id: str
    case_id: str
    action: str
    chat_id: int


def parse_callback_query(payload: dict[str, Any]) -> CallbackQuery:
    """Extract one callback query from a Telegram update.

    Wire format: callback_query.id, from.id, data = "<case_id>|<action>".
    Raises CallbackError for anything malformed or with an unknown action so
    the caller can answer 200-and-ignore without touching the pipeline.
    """
    cq = payload.get("callback_query")
    if not isinstance(cq, dict):
        raise CallbackError("not a callback query")
    callback_id = cq.get("id")
    if not isinstance(callback_id, str) or not callback_id:
        raise CallbackError("missing callback id")
    frm = cq.get("from") or {}
    chat_id = frm.get("id")
    if not isinstance(chat_id, int):
        raise CallbackError("missing presser id")
    data = cq.get("data")
    if not isinstance(data, str) or "|" not in data:
        raise CallbackError("malformed callback data")
    case_id, _, action = data.partition("|")
    if not case_id or action not in ALLOWED_ACTIONS:
        raise CallbackError("unknown case or action")
    return CallbackQuery(callback_id=callback_id, case_id=case_id, action=action, chat_id=chat_id)


def _case_age_s(case: dict[str, Any], now_f: float) -> float:
    """Age since the case was created or already decided.

    Explicit None checks: timestamp 0.0 is legitimate and must not be
    skipped by truthiness.
    """
    reference = case.get("decided_at")
    if reference is None:
        reference = case.get("created_at")
    if reference is None:
        return 0.0
    return max(0.0, now_f - float(reference))


def resolve_callback(
    query: CallbackQuery,
    store: CaseCallbackStore,
    *,
    now: float | None = None,
) -> tuple[str, str]:
    """Apply one button press. Returns (outcome, member_visible_text).

    Outcomes: applied | expired | missing_case | duplicate.
    Duplicate decisions are idempotent: first decision wins, later presses on
    an already-decided case are acknowledged without changing history.
    """
    now_f = now if now is not None else time.time()
    case = store.get(query.case_id)
    if case is None:
        return "missing_case", _EXPIRED_TEXT

    if case.get("decided_at"):
        return "duplicate", _DECIDED_TEXT

    if _case_age_s(case, now_f) > CALLBACK_TTL_SECONDS:
        return "expired", _EXPIRED_TEXT

    store.record_decision(query.case_id, f"tg:{query.chat_id}", query.action, now_f)
    return "applied", _DECIDED_TEXT
