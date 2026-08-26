"""Guardian agent: composes the human-facing package (doc 04 section 7).

Pure policy composition over upstream findings: no model calls at all in P2.
Verdict mapping is deterministic from evidence, thresholds from settings, so
the whole decision path is reproducible and auditable.

Verdict policy (graduated, doc 19 section 3):
- any issuer/rail FAIL -> SCAM (confidence from evidence weights)
- domain INCONCLUSIVE + strong triage -> SUSPICIOUS
- everything else -> SAFE (silent path)
"""

from __future__ import annotations

from gatehouse.agents.schemas import (
    GraphFinding,
    GuardianPackage,
    TriageResult,
    Verdict,
    VerificationFinding,
)
from gatehouse.config import Settings


def _round(v: float) -> float:
    return round(v, 4)


def compose_package(
    triage: TriageResult,
    verify_findings: tuple[VerificationFinding, ...] | list[VerificationFinding],
    graph: GraphFinding,
    settings: Settings,
) -> GuardianPackage:
    """Deterministic composition of the final verdict package."""
    findings = list(verify_findings)
    reason_codes: list[str] = []
    evidence: list[str] = []
    # Model degradation must survive to the bundle: a RULE_ reason with a
    # model configured means the model leg failed; a model_error prefix
    # means it failed loudly. Either way the consumer sees it.
    degraded: list[str] = []
    if triage.reason_code.startswith("model_error:"):
        degraded.append("TRIAGE_MODEL_FALLBACK")

    hard_fails = [f for f in findings if f.result == "FAIL"]
    inconclusives = [f for f in findings if f.result == "INCONCLUSIVE"]

    verdict: Verdict
    confidence: float

    # Issuer-verified kill switch: when every link in the message resolves
    # inside an official issuer domain and the issuer claim itself PASSes,
    # a SCREEN band driven only by link presence is a false positive by
    # definition. Genuine bank traffic must not park in the review queue.
    domain_findings = [f for f in findings if f.check_type == "domain_intel"]
    issuer_verified = any(f.check_type == "issuer_rule" and f.result == "PASS" for f in findings)
    links_all_verified = (
        bool(domain_findings)
        and all(f.result == "PASS" for f in domain_findings)
        and issuer_verified
    )

    if links_all_verified and triage.signal_class == "SCREEN" and not hard_fails:
        verdict = "SAFE"
        confidence = _round(max(0.75, 1.0 - triage.confidence))
        reason_codes.append("ISSUER_VERIFIED")
        evidence.append("all links resolve inside the claimed issuer's official domain")
    elif hard_fails:
        verdict = "SCAM"
        weights = [f.weight for f in hard_fails]
        confidence = min(1.0, 0.70 + 0.10 * len(weights) + max(weights) * 0.2)
        for f in hard_fails:
            reason_codes.append(f"HARD_FAIL_{f.check_type.upper()}")
            evidence.append(f.evidence_ref)
        if triage.payment_intent:
            reason_codes.append("PAYMENT_INTENT")
        if graph.prior_events > 0:
            reason_codes.append("GRAPH_PRIOR_EVENTS")
            evidence.append(f"{graph.prior_events} prior graph events on these identifiers")
            confidence = min(1.0, confidence + 0.05)
    elif triage.signal_class in ("SCREEN", "DECISION", "EMERGENCY"):
        verdict = "SUSPICIOUS"
        confidence = _round(max(0.45, min(0.85, triage.confidence)))
        reason_codes.append(f"TRIAGE_{triage.signal_class}")
        if inconclusives:
            reason_codes.append("DOMAIN_UNVERIFIED")
            evidence.extend(f"unverified link: {f.subject}" for f in inconclusives[:2])
        if triage.payment_intent:
            reason_codes.append("PAYMENT_INTENT")
    elif (graph.prior_events >= 1 and graph.max_taint >= 0.55) or graph.prior_events >= 3:
        # Repeat-offender identifiers escalate a quiet triage: a tainted
        # identifier reappearing anywhere is suspicious; a high-volume
        # identifier (3+ cases) is suspicious even if individually untainted
        # (mass-targeting shape). This is the cross-household moat working.
        verdict = "SUSPICIOUS"
        confidence = _round(min(0.85, 0.45 + 0.1 * graph.prior_events + graph.max_taint * 0.2))
        reason_codes.append("GRAPH_REPEAT_OFFENDER")
        evidence.append(
            f"{graph.prior_events} prior events, taint {graph.max_taint} on these identifiers"
        )
    else:
        verdict = "SAFE"
        confidence = _round(max(0.0, 1.0 - triage.confidence))
        reason_codes.append("NO_RISK_SIGNALS")

    if graph.unavailable:
        degraded.append("GRAPH_UNAVAILABLE")

    # recommended action catalog (pack-driven in later phases)
    if verdict == "SCAM":
        action = "warn_member"
    elif verdict == "SUSPICIOUS":
        action = "review_bundle"
    else:
        action = "none"

    return GuardianPackage(
        verdict=verdict,
        confidence=_round(confidence),
        reason_codes=reason_codes,
        top_evidence=evidence[:3],
        recommended_action=action,
        degraded_flags=degraded,
    )
