"""Tests for the Strands tool-driven investigator.

These drive a REAL strands Agent loop against the scripted mock model: the
tools, the tool registry, and the loop are the production ones, and only the
token-level model is doubled. That is the point of the file. A test that
called the tool functions directly would prove nothing about whether the
agent can actually reach them.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from gatehouse.agents.schemas import GraphFinding

pytest.importorskip("strands")

from gatehouse.agents.investigator import (
    TOOL_BRAND_CLAIM,
    TOOL_LINK_REPUTATION,
    TOOL_PAYMENT_HANDLES,
    TOOL_PRIOR_EVENTS,
    Collector,
    build_tools,
    run_investigation,
)
from gatehouse.agents.mock_model import MockModel
from gatehouse.packs.loader import load_pack
from gatehouse.packs.schemas import CountryPack

PACK_PATH = Path(__file__).resolve().parents[2] / "packs" / "in" / "pack.yaml"

SPOOF_TEXT = "SBI alert: your KYC expires today, update at http://sbi-verify.top/kyc"
CLEAN_TEXT = "Beta, dinner at 8 today. Bring the kids."


@pytest.fixture(scope="module")
def pack() -> CountryPack:
    return load_pack(PACK_PATH)


def _graph(prior: int = 0, unavailable: bool = False) -> GraphFinding:
    return GraphFinding(
        identifiers=[],
        prior_events=prior,
        max_taint=0.0,
        unavailable=unavailable,
    )


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _script(*tools: str) -> list[dict[str, Any]]:
    """Scripted agent turns: call each tool in order, then answer in text."""
    return [{"tool": t, "input": {}} for t in tools] + [{"text": "evidence gathered"}]


class TestAgentLoopReachesTools:
    def test_agent_loop_actually_calls_a_tool(self, pack: CountryPack) -> None:
        """The whole premise: a real Agent can reach our tool registry."""
        result = _run(
            run_investigation(
                SPOOF_TEXT,
                pack,
                _graph(),
                MockModel(script=_script(TOOL_LINK_REPUTATION)),
            )
        )
        assert TOOL_LINK_REPUTATION in result.tools_called
        assert result.degraded_flags == ()

    def test_multi_tool_investigation_collects_every_finding(self, pack: CountryPack) -> None:
        result = _run(
            run_investigation(
                SPOOF_TEXT,
                pack,
                _graph(),
                MockModel(script=_script(TOOL_LINK_REPUTATION, TOOL_BRAND_CLAIM)),
            )
        )
        assert TOOL_LINK_REPUTATION in result.tools_called
        assert TOOL_BRAND_CLAIM in result.tools_called
        kinds = {f.check_type for f in result.findings}
        assert "domain_intel" in kinds
        assert "issuer_rule" in kinds

    def test_spoof_produces_the_hard_fail_through_the_agent(self, pack: CountryPack) -> None:
        """A brand claim with an off-domain link must FAIL via the tool path
        exactly as it does deterministically. The agent changes who asks, not
        what the answer is."""
        result = _run(
            run_investigation(
                SPOOF_TEXT, pack, _graph(), MockModel(script=_script(TOOL_BRAND_CLAIM))
            )
        )
        fails = [f for f in result.findings if f.result == "FAIL"]
        assert fails, "brand spoof must fail the issuer rule"
        assert fails[0].check_type == "issuer_rule"


class TestEvidenceIntegrity:
    def test_tools_take_no_content_arguments(self, pack: CountryPack) -> None:
        """Doc 08: the model must have no channel to write into the evidence
        layer. Every investigator tool is closed over the signal instead."""
        tools = build_tools(SPOOF_TEXT, pack, _graph(), Collector())
        assert len(tools) == 4
        for tool in tools:
            spec = tool.tool_spec
            properties = spec["inputSchema"]["json"].get("properties", {})
            assert properties == {}, f"{spec['name']} accepts model-supplied input"

    def test_model_cannot_invent_a_finding(self, pack: CountryPack) -> None:
        """A clean message stays clean no matter how many tools the model runs."""
        result = _run(
            run_investigation(
                CLEAN_TEXT,
                pack,
                _graph(),
                MockModel(
                    script=_script(TOOL_LINK_REPUTATION, TOOL_BRAND_CLAIM, TOOL_PAYMENT_HANDLES)
                ),
            )
        )
        assert result.findings == ()
        assert len(result.tools_called) == 3

    def test_repeated_tool_calls_do_not_duplicate_findings(self, pack: CountryPack) -> None:
        result = _run(
            run_investigation(
                SPOOF_TEXT,
                pack,
                _graph(),
                MockModel(
                    script=_script(TOOL_LINK_REPUTATION, TOOL_LINK_REPUTATION, TOOL_LINK_REPUTATION)
                ),
            )
        )
        subjects = [(f.subject, f.check_type) for f in result.findings]
        assert len(subjects) == len(set(subjects))


class TestGraphTool:
    def test_graph_outage_is_disclosed_not_guessed(self, pack: CountryPack) -> None:
        result = _run(
            run_investigation(
                SPOOF_TEXT,
                pack,
                _graph(unavailable=True),
                MockModel(script=_script(TOOL_PRIOR_EVENTS)),
            )
        )
        assert TOOL_PRIOR_EVENTS in result.tools_called
        # An outage yields no correlation findings, and never a fabricated one.
        assert all(f.check_type != "graph" for f in result.findings)


class TestDegradation:
    def test_model_failure_falls_back_to_the_full_sweep(self, pack: CountryPack) -> None:
        """Charter principle 5: a dead model leg loses no evidence."""

        class BoomModel:
            pass

        result = _run(run_investigation(SPOOF_TEXT, pack, _graph(), BoomModel()))
        assert any(f.startswith("INVESTIGATOR_FALLBACK") for f in result.degraded_flags)
        assert result.findings, "fallback must still carry deterministic findings"
        assert any(f.result == "FAIL" for f in result.findings)

    def test_loop_that_calls_nothing_is_swept_and_flagged(self, pack: CountryPack) -> None:
        """An empty evidence set would read downstream as checked-and-clean."""
        result = _run(
            run_investigation(
                SPOOF_TEXT, pack, _graph(), MockModel(script=[{"text": "looks fine to me"}])
            )
        )
        assert result.degraded_flags == ("INVESTIGATOR_NO_TOOL_CALLS",)
        assert any(f.result == "FAIL" for f in result.findings)


class TestParityWithDeterministicPath:
    @pytest.mark.parametrize("text", [SPOOF_TEXT, CLEAN_TEXT])
    def test_full_toolset_matches_the_deterministic_sweep(
        self, pack: CountryPack, text: str
    ) -> None:
        """Running every tool must reproduce verify_signal exactly. The agent
        is allowed to choose which checks run; it is not allowed to change
        what a check concludes."""
        from gatehouse.agents.verify import verify_signal

        result = _run(
            run_investigation(
                text,
                pack,
                _graph(),
                MockModel(
                    script=_script(TOOL_LINK_REPUTATION, TOOL_BRAND_CLAIM, TOOL_PAYMENT_HANDLES)
                ),
            )
        )
        expected = {
            (f.subject, f.check_type, f.result, f.evidence_ref)
            for f in verify_signal(text, pack).findings
        }
        actual = {(f.subject, f.check_type, f.result, f.evidence_ref) for f in result.findings}
        assert actual == expected


class TestPipelineWiring:
    """The flag-gated stage inside investigate(), doc 04 section 4."""

    def _store(self) -> Any:
        from gatehouse.graph.store import InMemoryGraphStore

        return InMemoryGraphStore()

    def _settings(self, enabled: bool) -> Any:
        from gatehouse.config import Settings

        return Settings(environment="local", investigator_agent_enabled=enabled)

    def test_disabled_by_default_leaves_the_pipeline_untouched(self, pack: CountryPack) -> None:
        """The published numbers were measured with this off; it stays off."""
        from gatehouse.config import Settings
        from gatehouse.orchestrator import investigate

        assert Settings(environment="local").investigator_agent_enabled is False
        result = _run(
            investigate(
                "case-off",
                SPOOF_TEXT,
                pack,
                self._store(),
                settings=self._settings(False),
                model=MockModel(script=_script(TOOL_LINK_REPUTATION)),
            )
        )
        # The scripted model carries no triage payload, so the triage leg
        # degrades here; what matters is that no investigator stage ran.
        assert not any(f.startswith("INVESTIGATOR_") for f in result.degraded_flags)
        assert any(f.result == "FAIL" for f in (result.verify_findings or []))

    def test_enabled_stage_gathers_evidence_through_the_agent(self, pack: CountryPack) -> None:
        from gatehouse.orchestrator import investigate

        result = _run(
            investigate(
                "case-on",
                SPOOF_TEXT,
                pack,
                self._store(),
                settings=self._settings(True),
                model=MockModel(
                    script=_script(TOOL_LINK_REPUTATION, TOOL_BRAND_CLAIM, TOOL_PRIOR_EVENTS)
                ),
            )
        )
        assert result.verdict in ("SCAM", "SUSPICIOUS")
        assert not any(f.startswith("INVESTIGATOR_") for f in result.degraded_flags)

    def test_enabled_stage_never_empties_the_evidence_set(self, pack: CountryPack) -> None:
        """A loop that calls no tool must still leave the spoof failing."""
        from gatehouse.orchestrator import investigate

        result = _run(
            investigate(
                "case-lazy",
                SPOOF_TEXT,
                pack,
                self._store(),
                settings=self._settings(True),
                model=MockModel(script=[{"text": "nothing to see"}]),
            )
        )
        assert "INVESTIGATOR_NO_TOOL_CALLS" in result.degraded_flags
        assert any(f.result == "FAIL" for f in (result.verify_findings or []))
        assert result.verdict in ("SCAM", "SUSPICIOUS")

    def test_investigator_degradation_reaches_the_package(self, pack: CountryPack) -> None:
        """Principle 5: no quiet degradations, including this stage's."""
        from gatehouse.orchestrator import investigate

        class BoomModel:
            pass

        result = _run(
            investigate(
                "case-boom",
                SPOOF_TEXT,
                pack,
                self._store(),
                settings=self._settings(True),
                model=BoomModel(),
            )
        )
        assert any(f.startswith("INVESTIGATOR_FALLBACK") for f in result.degraded_flags)
        assert any(f.result == "FAIL" for f in (result.verify_findings or []))

    def test_breaker_refusal_is_disclosed_and_spends_nothing(self, pack: CountryPack) -> None:
        """An agent loop is several model calls; the spend cap governs it."""
        from gatehouse.orchestrator import investigate
        from gatehouse.spend import SpendMeter

        spent = SpendMeter(max_usd=0.02, max_calls=0)
        result = _run(
            investigate(
                "case-broke",
                SPOOF_TEXT,
                pack,
                self._store(),
                settings=self._settings(True),
                model=MockModel(script=_script(TOOL_LINK_REPUTATION)),
                meter=spent,
            )
        )
        assert "INVESTIGATOR_BUDGET_REFUSED" in result.degraded_flags
        assert result.spend_usd == 0.0
