"""Full-pipeline runner: flag mapping, taxonomy, gating, byte stability."""

from __future__ import annotations

import asyncio
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

from gatehouse.config import Settings
from gatehouse.constants import CLASS_NOISE, CLASS_SCREEN
from gatehouse.evaluation.run_full import _BAND_RANK, _flagged, run_split
from gatehouse.graph.store import InMemoryGraphStore
from gatehouse.orchestrator import CaseResult, investigate
from gatehouse.packs.loader import load_pack

PACK = Path(__file__).resolve().parents[2] / "packs" / "in" / "pack.yaml"


@lru_cache(maxsize=1)
def _dev_payload() -> dict[str, Any]:
    """One shared dev-split run; results are deterministic so caching is safe."""
    return run_split(PACK, "dev", 0.40)


def _result(
    verdict: str,
    triage_class: str,
    degraded: tuple[str, ...] = (),
) -> CaseResult:
    return CaseResult(
        case_id="c",
        triage_class=triage_class,
        triage_confidence=0.6,
        verdict=verdict,
        verdict_confidence=0.8,
        reason_codes=["R"],
        recommended_action="none",
        degraded_flags=list(degraded),
        spend_usd=0.0,
        canary="ghc_x",
    )


class TestFlagMapping:
    def test_suspicious_and_scam_flag(self) -> None:
        assert _flagged(_result("SUSPICIOUS", CLASS_NOISE))
        assert _flagged(_result("SCAM", CLASS_NOISE))

    def test_safe_never_flags(self) -> None:
        assert not _flagged(_result("SAFE", CLASS_SCREEN))

    def test_needs_human_flags_only_from_screen_or_above(self) -> None:
        assert _flagged(_result("NEEDS_HUMAN", CLASS_SCREEN))
        assert not _flagged(_result("NEEDS_HUMAN", CLASS_NOISE))

    def test_band_rank_is_not_alphabetical(self) -> None:
        assert _BAND_RANK["DECISION"] > _BAND_RANK["SCREEN"]
        assert _BAND_RANK["EMERGENCY"] == max(_BAND_RANK.values())

    def test_unknown_class_ranks_below_screen(self) -> None:
        assert not _flagged(_result("NEEDS_HUMAN", "MYSTERY_CLASS"))


class TestHoldoutGate:
    def test_run_split_refuses_bad_split_name(self) -> None:
        with pytest.raises(ValueError, match="unknown split"):
            run_split(PACK, "staging", 0.40)

    def test_main_requires_reason_for_holdout(self, capsys: pytest.CaptureFixture[str]) -> None:
        from gatehouse.evaluation import run_full

        with pytest.raises(SystemExit):
            run_full.main(["--split", "holdout"])
        assert "--confirm-holdout" in capsys.readouterr().err

    def test_main_requires_confirm_flag_for_holdout(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from gatehouse.evaluation import run_full

        with pytest.raises(SystemExit):
            run_full.main(["--split", "holdout", "--reason", "opening one"])
        assert "--confirm-holdout" in capsys.readouterr().err


class TestDevRun:
    def test_shape_and_runner_id(self) -> None:
        payload = _dev_payload()
        assert payload["runner"] == "full-pipeline-local-mock-v1"
        assert payload["cases"] == 480
        assert payload["tp"] + payload["fp"] + payload["tn"] + payload["fn"] == 480

    def test_zero_degraded_share_in_local_mock(self) -> None:
        assert _dev_payload()["degraded_case_share"] == 0.0

    def test_taxonomy_covers_all_classes(self) -> None:
        expected = {
            "missed_pattern_family",
            "language_gap",
            "verification_tool_gap",
            "threshold_miscalibration",
            "orchestration_bug",
            "degraded_mode_cause",
            "labeling_dispute",
        }
        taxonomy = _dev_payload()["failure_taxonomy"]
        assert expected == set(taxonomy.keys())
        # Current calibrated state: the suite must stay at zero misses.
        assert sum(taxonomy.values()) == 0

    def test_recall_bar_met(self) -> None:
        assert _dev_payload()["recall"] >= 0.85

    def test_false_gate_bar_met(self) -> None:
        assert _dev_payload()["false_gate_rate"] <= 0.05

    def test_payload_is_json_serializable_sorted_stable(self) -> None:
        once = json.dumps(_dev_payload(), indent=2, sort_keys=True)
        again = run_split(PACK, "dev", 0.40)
        assert once == json.dumps(again, indent=2, sort_keys=True)

    def test_floor_override_changes_behavior(self) -> None:
        strict = run_split(PACK, "dev", 0.60)
        baseline = run_split(PACK, "dev", 0.40)
        assert strict["recall"] < baseline["recall"]


class TestNoIdentifierEmptySemantics:
    def test_plain_message_graph_is_empty_not_unavailable(self) -> None:
        pack = load_pack(PACK)
        settings = Settings(rule_screen_floor=0.40)

        async def one() -> CaseResult:
            return await investigate(
                "case-empty-graph",
                "hello family, dinner at eight",
                pack,
                InMemoryGraphStore(),
                settings=settings,
                model=None,
            )

        result = asyncio.run(one())
        assert result.graph_finding is not None
        assert result.graph_finding.unavailable is False
        assert result.degraded_flags == []
