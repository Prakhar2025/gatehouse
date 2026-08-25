"""Tests for the evidence bundle shape and store."""

from __future__ import annotations

from typing import Any

from gatehouse.agents.schemas import (
    GraphFinding,
    GuardianPackage,
    TriageResult,
    VerificationFinding,
)
from gatehouse.channels.evidence import (
    DynamoBundleStore,
    InMemoryBundleStore,
    build_bundle,
    new_case_id,
)
from gatehouse.orchestrator import CaseResult


def _result() -> CaseResult:
    return CaseResult(
        case_id="case-1",
        triage_class="DECISION",
        triage_confidence=0.9,
        verdict="SCAM",
        verdict_confidence=0.93,
        reason_codes=["HARD_FAIL_ISSUER_RULE"],
        recommended_action="warn_member",
        degraded_flags=[],
        spend_usd=0.01,
        canary="ghc_abc",
    )


def _triage() -> TriageResult:
    return TriageResult(
        signal_class="DECISION", confidence=0.9, payment_intent=True, reason_code="R1"
    )


def _finds() -> list[VerificationFinding]:
    return [
        VerificationFinding(
            subject="SBI", check_type="issuer_rule", result="FAIL", evidence_ref="e", weight=0.5
        )
    ]


def _package() -> GuardianPackage:
    return GuardianPackage(
        verdict="SCAM",
        confidence=0.93,
        reason_codes=["HARD_FAIL_ISSUER_RULE"],
        top_evidence=["e"],
        recommended_action="warn_member",
        degraded_flags=[],
    )


class TestBuildBundle:
    def test_binds_all_components(self) -> None:
        bundle = build_bundle(
            case_result=_result(),
            triage=_triage(),
            verify_findings=_finds(),
            graph=GraphFinding(prior_events=2, max_taint=0.7),
            package=_package(),
            household_id="fam-1",
            channel="telegram",
            raw_text_redacted="[REDACTED]",
            now=1000.0,
        )
        assert bundle.case_id == "case-1"
        assert bundle.household_id == "fam-1"
        assert bundle.channel == "telegram"
        assert bundle.revision == 1
        assert bundle.verdict == "SCAM"
        assert bundle.reason_codes == ("HARD_FAIL_ISSUER_RULE",)
        assert bundle.top_evidence == ("e",)
        assert bundle.created_at == 1000.0


class TestNewCaseId:
    def test_unique(self) -> None:
        ids = {new_case_id() for _ in range(1000)}
        assert len(ids) == 1000

    def test_short(self) -> None:
        assert len(new_case_id()) == 16


class TestInMemoryBundleStore:
    def test_write_and_latest_round_trip(self) -> None:
        store = InMemoryBundleStore()
        bundle = build_bundle(
            case_result=_result(),
            triage=_triage(),
            verify_findings=_finds(),
            graph=GraphFinding(),
            package=_package(),
            household_id="fam-1",
            channel="telegram",
            raw_text_redacted="",
        )
        result = store.write(bundle)
        assert result["written"] is True
        latest = store.latest("fam-1", "case-1")
        assert latest is not None
        assert latest.verdict == "SCAM"

    def test_latest_returns_none_when_absent(self) -> None:
        store = InMemoryBundleStore()
        assert store.latest("fam-1", "case-1") is None


class _FakeDynamo:
    def __init__(self) -> None:
        self.puts: list[dict[str, Any]] = []
        self._items: dict[tuple[str, str], dict[str, Any]] = {}

    def put_item(self, **kwargs: Any) -> dict[str, Any]:
        self.puts.append(kwargs)
        item = kwargs["Item"]
        key = (item["pk"]["S"], item["sk"]["S"])
        self._items[key] = item
        return {}


class TestDynamoBundleStore:
    def test_write_includes_required_attrs(self) -> None:
        fake = _FakeDynamo()
        store = DynamoBundleStore(fake, "gatehouse-cases")
        bundle = build_bundle(
            case_result=_result(),
            triage=_triage(),
            verify_findings=_finds(),
            graph=GraphFinding(),
            package=_package(),
            household_id="fam-1",
            channel="telegram",
            raw_text_redacted="",
            now=2000.0,
        )
        store.write(bundle)
        item = fake.puts[0]["Item"]
        assert item["pk"]["S"] == "HOUSEHOLD#fam-1"
        assert item["sk"]["S"].startswith("CASE#case-1#BUNDLE#0001")
        assert item["verdict"]["S"] == "SCAM"
        assert item["canary"]["S"] == "ghc_abc"
        assert "HARD_FAIL_ISSUER_RULE" in item["reason_codes"]["SS"]
