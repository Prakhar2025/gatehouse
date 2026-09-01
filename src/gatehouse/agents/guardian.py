"""Guardian agent: composes the human-facing package (doc 04 section 7).

Pure policy composition over upstream findings: no model calls at all in P2.
Verdict mapping is deterministic from evidence, thresholds from settings, so
the whole decision path is reproducible and auditable.

Verdict policy:
- any issuer/rail FAIL -> SCAM (confidence from evidence weights)
- domain INCONCLUSIVE + strong triage -> SUSPICIOUS
- everything else -> SAFE (silent path)

Every package additionally carries its silence band (doc 19 section 3), which
governs whether a human is paged and is the contract the passive arrival
filters consume. See compute_silence_band.
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
from gatehouse.constants import (
    BAND_AGENT_SCREEN,
    BAND_BADGED_RING,
    BAND_PASS,
    BAND_SILENT_KILL,
    SilenceBand,
)


def _round(v: float) -> float:
    return round(v, 4)


def compute_silence_band(
    verdict: Verdict,
    confidence: float,
    settings: Settings,
    degraded: bool = False,
) -> SilenceBand:
    """Map a composed verdict onto the graduated silence law (doc 19 section 3).

    Silence is earned, never assumed, so the ladder is deliberately
    conservative in four places:

    - A degraded case is never silenced. Some dependency did not answer, so
      the confidence attached to this verdict was computed on partial
      evidence. Handling that in silence would hide both the case and the
      outage, and an operator who cannot see degradation cannot fix it
      (charter principle 5).

    - NEEDS_HUMAN is the pipeline explicitly asking for a person. It can never
      be silenced, whatever the confidence attached to it.
    - Only SCAM reaches SILENT_KILL. SUSPICIOUS means the evidence did not
      settle, and an unsettled case is not something to handle in silence
      however high the number next to it reads.
    - SAFE means no threat was found, which is PASS: invisible processing,
      not a suppressed alarm.

    Thresholds come from settings so one environment variable moves the
    operating point, and doc 19 acceptance criterion 2 is satisfied by
    configuration rather than by a code change.
    """
    if verdict == "NEEDS_HUMAN":
        return BAND_BADGED_RING
    if verdict == "SAFE":
        return BAND_PASS
    if verdict == "SCAM" and confidence >= settings.silent_kill_floor and not degraded:
        return BAND_SILENT_KILL
    if confidence >= settings.gray_band_high:
        return BAND_AGENT_SCREEN
    if confidence >= settings.gray_band_low:
        return BAND_BADGED_RING
    return BAND_PASS


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
    # Degradation must survive to the bundle: a RULE_ reason with a model
    # configured means the model leg failed; model_error means it failed
    # loudly; budget_refused means the breaker stopped it. None of these may
    # reach a human invisible (charter principle 5).
    degraded: list[str] = []
    if triage.reason_code.startswith("model_error:"):
        degraded.append("TRIAGE_MODEL_FALLBACK")
    elif triage.reason_code == "budget_refused":
        degraded.append("TRIAGE_BUDGET_REFUSED")

    hard_fails = [f for f in findings if f.result == "FAIL"]
    inconclusives = [f for f in findings if f.result == "INCONCLUSIVE"]

    verdict: Verdict
    confidence: float

    # Issuer-verified kill switch: when every link in the message resolves
    # inside an official issuer domain and the issuer claim itself PASSes,
    # a SCREEN band driven only by link presence is a false positive by
    # definition. Genuine bank traffic must not park in the review queue.
    # A DECISION band receives the same rescue under stricter guards: the
    # model leg can panic on branded delivery and government traffic
    # (observed live: a genuine BlueDart tracking message scored >= 0.85),
    # and a claim-rule PASS is exactly the evidence that caps that panic.
    # The payment-intent guard keeps the credibility-link attack shape
    # escalated: a real brand link plus a pay-now ask is still a decision.
    domain_findings = [f for f in findings if f.check_type == "domain_intel"]
    issuer_verified = any(f.check_type == "issuer_rule" and f.result == "PASS" for f in findings)
    # Trusted rescue requires the message to CLAIM a trusted party. A link
    # alone proves nothing (any scam carries a link); the claim is what the
    # domain check adjudicates.
    claims_issuer = any(f.check_type == "issuer_rule" for f in findings)
    links_all_verified = (
        bool(domain_findings)
        and all(f.result == "PASS" for f in domain_findings)
        and (issuer_verified or claims_issuer)
    )

    verified_kill_switch = (
        links_all_verified
        and not hard_fails
        and (
            triage.signal_class == "SCREEN"
            or (
                triage.signal_class == "DECISION"
                and issuer_verified
                and (
                    not triage.payment_intent
                    # A payment ASK with no payment HANDLE is benign: genuine
                    # COD notes say pay, but carry no VPA, phone, or UTR the
                    # money could actually leave through. The credibility-link
                    # attack always carries an extractable handle.
                    or not graph.identifiers
                )
            )
        )
    )

    # Channel-free cap: a message that offers no action handle (no link to
    # adjudicate, no phone, no VPA, no UTR, no payment ask) cannot move
    # anyone's money in a forwarding context; the gate guards actions, and
    # there is none to guard. Model-leg panic on OTP forwards and linkless
    # brand offers lands here (staging eval 2026-08-27: 30.6 percent false
    # gates, every miss channel-free). Two hard limits keep this a cap on
    # model opinion and nothing else:
    # - the band must be MODEL-driven; deterministic rule evidence never gets
    #   capped, or text-only scam scripts would lose their escalation,
    # - the rule leg's own conclusion must be weak (NOISE or INFO): when the
    #   rules independently call it SCREEN or worse, two detectors agreeing
    #   outranks one channel-absence heuristic.
    # Emergency bands and hard evidence always escalate regardless.
    model_panic_band = triage.band_source == "model" and triage.rule_class in ("NOISE", "INFO")
    channel_free = not domain_findings and not graph.identifiers and not triage.payment_intent
    channel_free_cap = (
        channel_free
        and not hard_fails
        and triage.signal_class in ("SCREEN", "DECISION")
        and model_panic_band
    )

    if verified_kill_switch:
        verdict = "SAFE"
        confidence = _round(max(0.75, 1.0 - triage.confidence))
        reason_codes.append("ISSUER_VERIFIED")
        evidence.append("all links resolve inside the claimed issuer's official domain")
    elif channel_free_cap:
        verdict = "SAFE"
        confidence = _round(max(0.60, 1.0 - triage.confidence))
        reason_codes.append("NO_ACTION_CHANNEL")
        evidence.append("no link, phone, VPA, or payment ask present: nothing to act on")
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

    final_confidence = _round(confidence)
    return GuardianPackage(
        verdict=verdict,
        confidence=final_confidence,
        reason_codes=reason_codes,
        top_evidence=evidence[:3],
        recommended_action=action,
        degraded_flags=degraded,
        silence_band=compute_silence_band(
            verdict, final_confidence, settings, degraded=bool(degraded)
        ),
    )
