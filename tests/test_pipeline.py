"""Tests for verify, guardian composition, and the full orchestrator pipeline."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from gatehouse.agents.guardian import compose_package
from gatehouse.agents.mock_model import MockModel
from gatehouse.agents.schemas import GraphFinding, TriageResult, VerificationFinding
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
