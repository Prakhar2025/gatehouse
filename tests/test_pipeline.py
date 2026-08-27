"""Tests for verify, guardian composition, and the full orchestrator pipeline."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from gatehouse.agents.guardian import compose_package
from gatehouse.agents.mock_model import MockModel
from gatehouse.agents.schemas import (
    GraphFinding,
    GraphIdentifier,
    TriageResult,
    VerificationFinding,
)
from gatehouse.agents.verify import verify_signal
from gatehouse.config import Settings
from gatehouse.graph.store import InMemoryGraphStore
from gatehouse.orchestrator import investigate
from gatehouse.packs.loader import load_pack
from gatehouse.packs.schemas import CountryPack

REPO = Path(__file__).resolve().parents[1]
PACK = REPO / "packs" / "in" / "pack.yaml"

H1 = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"


def go(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(scope="module")
def pack() -> CountryPack:
    return load_pack(PACK)


class TestVerify:
    def test_trusted_issuer_url_passes(self, pack: CountryPack) -> None:
        out = verify_signal("check https://www.onlinesbi.sbi login", pack)
        assert any(f.result == "PASS" and f.subject.endswith("onlinesbi.sbi") for f in out.findings)

    def test_unknown_domain_inconclusive_not_fail(self, pack: CountryPack) -> None:
        out = verify_signal("click http://random-site.example now", pack)
        matches = [f for f in out.findings if "random-site" in f.subject]
        assert matches and matches[0].result == "INCONCLUSIVE"

    def test_bank_name_with_foreign_link_fails(self, pack: CountryPack) -> None:
        out = verify_signal("SBI alert, verify at http://sbi-kyc-verify.top", pack)
        fails = [f for f in out.fails if f.check_type == "issuer_rule"]
        assert fails and "SBI" in fails[0].subject

    def test_malformed_vpa_fails_rail_check(self, pack: CountryPack) -> None:
        out = verify_signal("pay to foo@12345 now", pack)
        assert any(f.check_type == "rail_format" and f.result == "FAIL" for f in out.findings)


class TestGuardian:
    def test_hard_fail_means_scam(self, pack: CountryPack) -> None:
        s = Settings()
        triage = TriageResult(
            signal_class="DECISION", confidence=0.9, payment_intent=True, reason_code="R1"
        )
        fail = VerificationFinding(
            subject="SBI", check_type="issuer_rule", result="FAIL", evidence_ref="e", weight=0.5
        )
        pkg = compose_package(triage, [fail], GraphFinding(), s)
        assert pkg.verdict == "SCAM"
        assert "HARD_FAIL_ISSUER_RULE" in pkg.reason_codes
        assert pkg.recommended_action == "warn_member"

    def test_verified_claim_caps_model_panic_decision(self, pack: CountryPack) -> None:
        """Live-observed shape: the model leg scored a genuine BlueDart
        tracking message into the DECISION band. When every link resolves
        inside the claimed party's official domains and the claim rule
        PASSes, verified evidence must cap that panic: SAFE, disclosed as
        issuer-verified."""
        s = Settings()
        triage = TriageResult(
            signal_class="DECISION", confidence=0.86, payment_intent=False, reason_code="R9"
        )
        dom = VerificationFinding(
            subject="www.bluedart.com",
            check_type="domain_intel",
            result="PASS",
            evidence_ref="trusted_domain:bluedart.com",
            weight=0.85,
        )
        claim = VerificationFinding(
            subject="BlueDart",
            check_type="issuer_rule",
            result="PASS",
            evidence_ref="claims BlueDart and links resolve inside bluedart.com",
            weight=0.9,
        )
        pkg = compose_package(triage, [dom, claim], GraphFinding(), s)
        assert pkg.verdict == "SAFE"
        assert "ISSUER_VERIFIED" in pkg.reason_codes

    def test_credibility_attack_with_handle_still_escalates(self, pack: CountryPack) -> None:
        """Credibility-link attack shape refined against the COD reality:
        a real brand link plus a payment ASK plus an extractable money
        HANDLE (VPA/phone/UTR) escalates even though every link verifies.
        The handle is what makes collection possible."""
        s = Settings()
        triage = TriageResult(
            signal_class="DECISION",
            confidence=0.9,
            payment_intent=True,
            reason_code="R10",
            band_source="model",
        )
        dom = VerificationFinding(
            subject="www.bluedart.com",
            check_type="domain_intel",
            result="PASS",
            evidence_ref="trusted_domain:bluedart.com",
            weight=0.85,
        )
        claim = VerificationFinding(
            subject="BlueDart",
            check_type="issuer_rule",
            result="PASS",
            evidence_ref="claims BlueDart and links resolve inside bluedart.com",
            weight=0.9,
        )
        pkg = compose_package(
            triage,
            [dom, claim],
            GraphFinding(
                identifiers=[GraphIdentifier(kind="VPA", hashed_value="h4sh1value9876543")],
                prior_events=0,
            ),
            s,
        )
        assert pkg.verdict == "SUSPICIOUS"
        assert "PAYMENT_INTENT" in pkg.reason_codes

    def test_verified_cod_note_without_handle_is_safe(self, pack: CountryPack) -> None:
        """Genuine cash-on-delivery notes say pay while carrying only the
        brand's own link and no collectable handle: with zero extracted
        identifiers there is nothing to act on, so the model's DECISION
        panic gets capped despite the payment word."""
        s = Settings()
        triage = TriageResult(
            signal_class="DECISION",
            confidence=0.9,
            payment_intent=True,
            reason_code="R10b",
            band_source="model",
        )
        dom = VerificationFinding(
            subject="www.bluedart.com",
            check_type="domain_intel",
            result="PASS",
            evidence_ref="trusted_domain:bluedart.com",
            weight=0.85,
        )
        claim = VerificationFinding(
            subject="BlueDart",
            check_type="issuer_rule",
            result="PASS",
            evidence_ref="claims BlueDart and links resolve inside bluedart.com",
            weight=0.9,
        )
        pkg = compose_package(triage, [dom, claim], GraphFinding(), s)
        assert pkg.verdict == "SAFE"
        assert "ISSUER_VERIFIED" in pkg.reason_codes

    def test_unadjudicated_claim_never_caps_decision(self, pack: CountryPack) -> None:
        """A DECISION with links passing the domain tier but no PASS on the
        claim rule itself is not verified evidence; it stays escalated."""
        s = Settings()
        triage = TriageResult(
            signal_class="DECISION", confidence=0.88, payment_intent=False, reason_code="R11"
        )
        dom = VerificationFinding(
            subject="www.bluedart.com",
            check_type="domain_intel",
            result="PASS",
            evidence_ref="trusted_domain:bluedart.com",
            weight=0.85,
        )
        pkg = compose_package(triage, [dom], GraphFinding(), s)
        assert pkg.verdict == "SUSPICIOUS"

    def test_channel_free_model_panic_capped_to_safe(self, pack: CountryPack) -> None:
        """Staging-observed shape: the model leg scored a member's own OTP
        forward into DECISION. No link, no phone, no VPA, no payment ask:
        nothing can act on this message, so it must not interrupt anyone."""
        s = Settings()
        triage = TriageResult(
            signal_class="DECISION",
            confidence=0.92,
            payment_intent=False,
            reason_code="R12",
            band_source="model",
        )
        pkg = compose_package(triage, [], GraphFinding(), s)
        assert pkg.verdict == "SAFE"
        assert "NO_ACTION_CHANNEL" in pkg.reason_codes

    def test_rule_driven_band_is_never_capped(self, pack: CountryPack) -> None:
        """Same channel-free shape, but the deterministic rule leg itself
        demanded the band: deterministic evidence never gets capped, or
        text-only scam scripts would lose their escalation."""
        s = Settings()
        triage = TriageResult(
            signal_class="DECISION",
            confidence=0.92,
            payment_intent=False,
            reason_code="RULE_DECISION",
            band_source="rules",
            rule_class="DECISION",
        )
        pkg = compose_package(triage, [], GraphFinding(), s)
        assert pkg.verdict == "SUSPICIOUS"

    def test_channel_free_screens_do_not_escalate(self, pack: CountryPack) -> None:
        """Linkless bank offers and newsletters in the SCREEN band with no
        action handle stay silent (staging miss family, 21 of 44)."""
        s = Settings()
        triage = TriageResult(
            signal_class="SCREEN",
            confidence=0.6,
            payment_intent=False,
            reason_code="R13",
            band_source="model",
        )
        pkg = compose_package(triage, [], GraphFinding(), s)
        assert pkg.verdict == "SAFE"

    def test_payment_ask_always_keeps_a_channel(self, pack: CountryPack) -> None:
        """payment_intent alone is an action handle: a money ask escalates
        even with no identifiers extracted yet and no verifying evidence."""
        s = Settings()
        triage = TriageResult(
            signal_class="DECISION",
            confidence=0.9,
            payment_intent=True,
            reason_code="R14",
            band_source="model",
        )
        pkg = compose_package(triage, [], GraphFinding(), s)
        assert pkg.verdict == "SUSPICIOUS"
        assert "PAYMENT_INTENT" in pkg.reason_codes

    def test_unverified_link_keeps_the_gate(self, pack: CountryPack) -> None:
        """A link that is not in any registry is an action channel of
        unknown reputation: INCONCLUSIVE must stay escalated."""
        s = Settings()
        triage = TriageResult(
            signal_class="SCREEN", confidence=0.6, payment_intent=False, reason_code="R15"
        )
        dom = VerificationFinding(
            subject="strange-shop.example",
            check_type="domain_intel",
            result="INCONCLUSIVE",
            evidence_ref="not_in_issuer_registry",
            weight=0.2,
        )
        pkg = compose_package(triage, [dom], GraphFinding(), s)
        assert pkg.verdict == "SUSPICIOUS"

    def test_extracted_identifier_keeps_the_gate(self, pack: CountryPack) -> None:
        """A phone or VPA in the text is an action channel: impersonation
        scripts hand the victim a number to send money to."""
        s = Settings()
        triage = TriageResult(
            signal_class="DECISION",
            confidence=0.7,
            payment_intent=False,
            reason_code="R16",
            band_source="model",
        )
        pkg = compose_package(
            triage,
            [],
            GraphFinding(
                identifiers=[GraphIdentifier(kind="VPA", hashed_value="a1b2c3d4e5f6a7b8")],
                prior_events=0,
            ),
            s,
        )
        assert pkg.verdict == "SUSPICIOUS"

    def test_emergency_band_never_capped(self, pack: CountryPack) -> None:
        """The channel-free cap covers SCREEN and DECISION only; an EMERGENCY
        triage always reaches a human."""
        s = Settings()
        triage = TriageResult(
            signal_class="EMERGENCY", confidence=0.9, payment_intent=False, reason_code="R17"
        )
        pkg = compose_package(triage, [], GraphFinding(), s)
        assert pkg.verdict == "SUSPICIOUS"

    def test_suspicious_band_without_fails(self, pack: CountryPack) -> None:
        s = Settings()
        triage = TriageResult(
            signal_class="SCREEN", confidence=0.6, payment_intent=False, reason_code="R2"
        )
        pkg = compose_package(triage, [], GraphFinding(), s)
        assert pkg.verdict == "SUSPICIOUS"
        assert pkg.recommended_action == "review_bundle"

    def test_safe_when_nothing_signals(self, pack: CountryPack) -> None:
        s = Settings()
        triage = TriageResult(
            signal_class="NOISE", confidence=0.1, payment_intent=False, reason_code="R3"
        )
        pkg = compose_package(triage, [], GraphFinding(), s)
        assert pkg.verdict == "SAFE"

    def test_graph_unavailable_flag_propagates(self, pack: CountryPack) -> None:
        s = Settings()
        triage = TriageResult(
            signal_class="SCREEN", confidence=0.6, payment_intent=False, reason_code="R4"
        )
        pkg = compose_package(triage, [], GraphFinding(unavailable=True), s)
        assert "GRAPH_UNAVAILABLE" in pkg.degraded_flags

    def test_model_error_becomes_visible_degradation(self, pack: CountryPack) -> None:
        """A triage that fell back to rules because the model errored must
        carry the fallback flag into the bundle; silent degradation is the
        one thing this system never does (charter principle 5)."""
        s = Settings()
        triage = TriageResult(
            signal_class="SCREEN",
            confidence=0.6,
            payment_intent=False,
            reason_code="model_error:ValidationException",
        )
        pkg = compose_package(triage, [], GraphFinding(), s)
        assert "TRIAGE_MODEL_FALLBACK" in pkg.degraded_flags


class TestOrchestrator:
    def test_full_pipeline_scam_flow(self, pack: CountryPack) -> None:
        store = InMemoryGraphStore()
        text = "SBI KYC expired, pay now at http://sbi-verify.top UTR123456789012"
        result = go(
            investigate(
                "case-1",
                text,
                pack,
                store,
                settings=Settings(environment="local"),
                model=MockModel(tool_payload={"scam_likelihood": 0.97, "reason_code": "KYC"}),
            )
        )
        assert result.verdict in ("SCAM", "SUSPICIOUS")
        assert result.canary.startswith("ghc_")
        assert result.spend_usd >= 0.0

    def test_benign_flow_is_safe(self, pack: CountryPack) -> None:
        store = InMemoryGraphStore()
        text = "lunch tomorrow at the usual place?"
        result = go(
            investigate(
                "case-2",
                text,
                pack,
                store,
                settings=Settings(environment="local"),
                model=MockModel(tool_payload={"scam_likelihood": 0.05, "reason_code": "NONE"}),
            )
        )
        assert result.verdict == "SAFE"
        assert result.recommended_action == "none"

    def test_graph_memory_across_cases(self, pack: CountryPack) -> None:
        """Repeat-scammer shape: tainted VPA reappearing must escalate case-b."""
        store = InMemoryGraphStore()
        text1 = "Your KYC has expired, pay now to scammer99@ybl"
        text2 = "final warning, send payment to scammer99@ybl today"
        go(investigate("case-a", text1, pack, store, settings=Settings(environment="local")))
        result2 = go(
            investigate("case-b", text2, pack, store, settings=Settings(environment="local"))
        )
        assert "GRAPH_REPEAT_OFFENDER" in result2.reason_codes
        assert result2.verdict == "SUSPICIOUS"
