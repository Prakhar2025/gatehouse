"""Shared Pydantic contracts for every agent (doc 04 section 2).

These models are the wire format between agents, the orchestrator, the console,
and the evaluation harness. Change them only with an eval impact note (doc 11
section 4). Extra fields are forbidden: a typo must fail loudly, never vanish.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

SignalClass = Literal["NOISE", "INFO", "SCREEN", "DECISION", "EMERGENCY"]
Verdict = Literal["SAFE", "SUSPICIOUS", "SCAM", "NEEDS_HUMAN"]
CheckType = Literal[
    "lexicon_rule",
    "issuer_rule",
    "domain_intel",
    "rail_format",
    "source_crosscheck",
    "temporal",
    "numerical",
]
CheckResult = Literal["PASS", "FAIL", "INCONCLUSIVE"]


class TriageResult(BaseModel):
    """Output of triage_agent."""

    model_config = ConfigDict(extra="forbid")

    signal_class: SignalClass
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    payment_intent: bool = False
    urgency_signals: list[str] = Field(default_factory=list)
    reason_code: str


class Claim(BaseModel):
    """One atomic factual claim extracted from a signal."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    text: Annotated[str, Field(min_length=1)]


class VerificationFinding(BaseModel):
    """Outcome of checking one claim or artifact."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str | None = None
    subject: Annotated[str, Field(min_length=1)]
    check_type: CheckType
    result: CheckResult
    evidence_ref: str = ""
    weight: float = 0.0


class GraphIdentifier(BaseModel):
    """One hashed identifier touched by the signal."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["PHONE", "VPA", "DOMAIN", "URL_PATH", "BANK_ACCT", "EMAIL", "UTR_REF"]
    hashed_value: Annotated[str, Field(min_length=16, max_length=64)]
    first_seen: str | None = None
    last_seen: str | None = None
    event_count: int = 0
    taint: Annotated[float, Field(ge=0.0, le=1.0)] = 0.0
    coverage_note: str = ""


class GraphFinding(BaseModel):
    """Output of graph_agent for one case."""

    model_config = ConfigDict(extra="forbid")

    identifiers: list[GraphIdentifier] = Field(default_factory=list)
    prior_events: int = 0
    max_taint: float = 0.0
    unavailable: bool = False


class GuardianPackage(BaseModel):
    """The single human-facing output of the whole pipeline."""

    model_config = ConfigDict(extra="forbid")

    verdict: Verdict
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    reason_codes: list[str] = Field(default_factory=list)
    top_evidence: list[str] = Field(default_factory=list)
    recommended_action: str
    degraded_flags: list[str] = Field(default_factory=list)


EngagementDirection = Literal["OUT", "IN", "BLOCKED", "MODEL_ERROR"]


class EngagementTurnRecord(BaseModel):
    """One transcript line. Blocked or errored turns persist no scammer text."""

    model_config = ConfigDict(extra="forbid")

    turn: Annotated[int, Field(ge=0)]
    direction: EngagementDirection
    text: str = ""
    firewall: str = "OK"


class EngagementResult(BaseModel):
    """Output of engage_agent for one case (doc 04 section 6)."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    outcome: str
    turns_used: Annotated[int, Field(ge=0)]
    transcript: list[EngagementTurnRecord] = Field(default_factory=list)
    intent_confidence: Annotated[float, Field(ge=0.0, le=1.0)] = 0.0
    reason_code: str = ""
    degraded_flags: list[str] = Field(default_factory=list)
