"""The orchestrator: deterministic pipeline over one signal (doc 04 section 1).

Sequence (code decides between stages, models decide within stages):

    fence -> triage -> verify -> graph -> guardian package

Budget gates run before every model-touching stage; failures degrade
explicitly with flags, never crash, never silently pass (charter principle 5).

Isolation law (P4): a stage may fail, the pipeline may not. Every dependency-
backed stage runs inside its own fault boundary and records the degradation
on the result; verification loss forces the honest NEEDS_HUMAN verdict
instead of a quiet SAFE. Only pure code (fence, policy composition) is
trusted to be total.

Every stage is timed into an optional CaseTrace so any case reconstructs end
to end from its single case_trace log line.
"""

from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from typing import Any

from gatehouse.agents.guardian import compose_package
from gatehouse.agents.investigator import run_investigation
from gatehouse.agents.schemas import (
    GraphFinding,
    GuardianPackage,
    TriageResult,
    VerificationFinding,
)
from gatehouse.agents.triage import run_triage
from gatehouse.agents.verify import verify_signal
from gatehouse.config import Settings, get_settings
from gatehouse.fencing import fence
from gatehouse.graph.hashing import extract_identifiers, hash_identifier
from gatehouse.graph.store import GraphStore, finding_empty, finding_unavailable
from gatehouse.logging_utils import get_logger
from gatehouse.packs.schemas import CountryPack
from gatehouse.spend import SpendMeter, get_hourly_breaker
from gatehouse.tracing import CaseTrace

log = get_logger("gatehouse.orchestrator")


@dataclass
class CaseResult:
    """Everything one investigation produced."""

    case_id: str
    triage_class: str
    triage_confidence: float
    verdict: str
    verdict_confidence: float
    reason_codes: list[str]
    recommended_action: str
    degraded_flags: list[str]
    spend_usd: float
    canary: str
    # Intermediate artifacts, carried so the evidence bundle builder does not
    # need to re-run any stage. Default None keeps existing callers working.
    triage_result: TriageResult | None = None
    verify_findings: list[VerificationFinding] | None = None
    graph_finding: GraphFinding | None = None
    package: GuardianPackage | None = None


def _stage(trace: CaseTrace | None, name: str) -> AbstractContextManager[object]:
    """Timed span when tracing, a no-op otherwise."""
    if trace is None:
        return nullcontext()
    return trace.stage(name)


def _fallback_package(reason: str) -> GuardianPackage:
    """The one honest answer when the pipeline itself cannot decide."""
    return GuardianPackage(
        verdict="NEEDS_HUMAN",
        confidence=0.0,
        reason_codes=[reason],
        top_evidence=[],
        recommended_action="review_bundle",
        degraded_flags=[reason],
    )


async def investigate(
    case_id: str,
    raw_text: str,
    pack: CountryPack,
    store: GraphStore,
    settings: Settings | None = None,
    model: Any | None = None,
    meter: SpendMeter | None = None,
    trace: CaseTrace | None = None,
) -> CaseResult:
    """Run the full pipeline over one signal."""
    s = settings or get_settings()
    meter = meter or SpendMeter(
        max_usd=s.max_usd_per_investigation,
        max_calls=s.max_model_calls_per_investigation,
        # The hour ceiling sits above every per-case budget: without it a
        # flood of forwards is a flood of independent budgets (principle 7).
        hourly=get_hourly_breaker(s.breaker_hourly_call_cap),
    )

    # 1) fence (pure normalization; total by construction)
    fenced = fence(raw_text, case_id)

    # 2) triage (model + rules, budget-gated inside its own boundary)
    try:
        with _stage(trace, "triage"):
            triage = await run_triage(
                case_id,
                raw_text,
                fenced,
                pack,
                meter=meter,
                model=model,
                screen_floor=s.rule_screen_floor,
            )
    except Exception as exc:
        log.warning("triage_stage_failed", extra={"extra_fields": {"error": type(exc).__name__}})
        triage = TriageResult(
            signal_class="SCREEN",
            confidence=0.5,
            reason_code=f"model_error:{type(exc).__name__}",
        )

    # 3) verify (deterministic checks; loss is visible, never silent)
    verify_out = None
    try:
        with _stage(trace, "verify"):
            verify_out = verify_signal(raw_text, pack)
    except Exception as exc:
        log.warning("verify_stage_failed", extra={"extra_fields": {"error": type(exc).__name__}})
    findings: list[VerificationFinding] = (
        list(verify_out.findings) if verify_out is not None else []
    )

    # 4) graph: hash identifiers at the boundary, learn, then query.
    # Learning happens BEFORE querying: this case's own identifiers are
    # recorded (taint from triage class), so repeat offenders accumulate.
    # Store outages degrade to an explicit unavailable finding (matrix row 3).
    pairs = extract_identifiers(raw_text)
    hashed = [(kind, hash_identifier(kind, value, s.graph_salt)) for kind, value in pairs]
    graph: GraphFinding
    try:
        with _stage(trace, "graph"):
            if hashed:
                taint_base = {
                    "EMERGENCY": 0.95,
                    "DECISION": 0.85,
                    "SCREEN": 0.55,
                    "INFO": 0.25,
                    "NOISE": 0.0,
                }.get(triage.signal_class, 0.3)
                store.upsert_event(hashed, taint_base=taint_base, case_id=case_id)
                graph = store.finding_for([h for _, h in hashed])
            else:
                # No identifiers to correlate is a NORMAL empty result, not
                # an outage: flagging it marked healthy cases degraded.
                graph = finding_empty()
    except Exception as exc:
        log.warning("graph_stage_failed", extra={"extra_fields": {"error": type(exc).__name__}})
        graph = finding_unavailable(f"graph_error:{type(exc).__name__}")

    # 4b) tool-driven investigation (doc 04 section 4, flag-gated).
    # The deterministic sweep above already ran and its findings are held, so
    # this stage can only replace a complete evidence set with another
    # complete one; a failing agent loop never leaves the gate emptier than
    # it found it. Runs after the graph so the correlation tool has something
    # real to report. Breaker-gated: an agent loop is several model calls and
    # must answer to the same spend cap as every other leg.
    investigation_flags: list[str] = []
    if s.investigator_agent_enabled and model is not None and verify_out is not None:
        if not meter.allow():
            investigation_flags = ["INVESTIGATOR_BUDGET_REFUSED"]
        else:
            try:
                with _stage(trace, "investigate"):
                    investigation = await run_investigation(raw_text, pack, graph, model)
                findings = list(investigation.findings)
                investigation_flags = list(investigation.degraded_flags)
            except Exception as exc:
                log.warning(
                    "investigate_stage_failed",
                    extra={"extra_fields": {"error": type(exc).__name__}},
                )
                investigation_flags = [f"INVESTIGATOR_STAGE_FAILED:{type(exc).__name__}"]

    # 5) guardian composition (pure policy over whatever survived upstream)
    package: GuardianPackage | None = None
    try:
        with _stage(trace, "guardian"):
            package = compose_package(triage, findings, graph, s)
    except Exception as exc:
        log.warning("guardian_stage_failed", extra={"extra_fields": {"error": type(exc).__name__}})

    if package is None:
        # Composition itself failed: refuse to guess, hand it to a human.
        package = _fallback_package("PIPELINE_FAULT")
    elif verify_out is None:
        # Verification could not run at all: a SAFE verdict here would be a
        # lie of absence. Force the honest incomplete verdict (matrix row 2).
        package = GuardianPackage(
            verdict="NEEDS_HUMAN",
            confidence=round(min(package.confidence, 0.5), 4),
            reason_codes=[*package.reason_codes, "VERIFICATION_UNAVAILABLE"],
            top_evidence=package.top_evidence,
            recommended_action="review_bundle",
            degraded_flags=[*package.degraded_flags, "VERIFY_UNAVAILABLE"],
        )

    if investigation_flags:
        # A degraded investigation must reach the bundle like every other
        # degradation; principle 5 admits no quiet ones.
        package = package.model_copy(
            update={"degraded_flags": [*package.degraded_flags, *investigation_flags]}
        )

    if trace is not None:
        # Reconstruction facts ride with the trace, set by the stage owner
        # itself so any caller gets a complete line.
        trace.note("verdict", package.verdict)
        trace.note("spend_usd", meter.total_usd)
        trace.note("degraded", package.degraded_flags)

    return CaseResult(
        case_id=case_id,
        triage_class=triage.signal_class,
        triage_confidence=triage.confidence,
        verdict=package.verdict,
        verdict_confidence=package.confidence,
        reason_codes=package.reason_codes,
        recommended_action=package.recommended_action,
        degraded_flags=package.degraded_flags,
        spend_usd=meter.total_usd,
        canary=fenced.canary,
        triage_result=triage,
        verify_findings=findings,
        graph_finding=graph,
        package=package,
    )
