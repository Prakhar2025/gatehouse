"""The orchestrator: deterministic pipeline over one signal (doc 04 section 1).

Sequence (code decides between stages, models decide within stages):

    fence -> triage -> [verify || graph] -> guardian package

Budget gates run before every model-touching stage; failures degrade
explicitly with flags, never crash, never silently pass (charter principle 5).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gatehouse.agents.guardian import compose_package
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
from gatehouse.graph.store import GraphStore, finding_unavailable
from gatehouse.packs.schemas import CountryPack
from gatehouse.spend import SpendMeter


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


async def investigate(
    case_id: str,
    raw_text: str,
    pack: CountryPack,
    store: GraphStore,
    settings: Settings | None = None,
    model: Any | None = None,
    meter: SpendMeter | None = None,
) -> CaseResult:
    """Run the full pipeline over one signal."""
    s = settings or get_settings()
    meter = meter or SpendMeter(
        max_usd=s.max_usd_per_investigation, max_calls=s.max_model_calls_per_investigation
    )

    # 1) fence
    fenced = fence(raw_text, case_id)

    # 2) triage (model + rules, budget-gated inside)
    triage = await run_triage(case_id, raw_text, fenced, pack, meter=meter, model=model)

    # 3) verify (deterministic in P2; parallel-ready: no shared state)
    verify_out = verify_signal(raw_text, pack)

    # 4) graph: hash identifiers at the boundary, learn, then query.
    # Learning happens BEFORE querying: this case's own identifiers are
    # recorded (taint from triage class), so repeat offenders accumulate.
    pairs = extract_identifiers(raw_text)
    hashed = [(kind, hash_identifier(kind, value, s.graph_salt)) for kind, value in pairs]
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
        graph = finding_unavailable("no identifiers in signal")

    # 5) guardian composition (pure policy)
    package = compose_package(triage, verify_out.findings, graph, s)

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
        verify_findings=list(verify_out.findings),
        graph_finding=graph,
        package=package,
    )
