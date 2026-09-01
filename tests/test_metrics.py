"""Tests for metrics: Wilson math and report aggregation."""

from __future__ import annotations

from pathlib import Path

import pytest

from gatehouse.evaluation.generator import MINI_SET_SIZE, generate_mini_set
from gatehouse.evaluation.metrics import build_report, wilson_interval
from gatehouse.evaluation.schemas import EvalCase, Report
from gatehouse.packs.schemas import STRATA_ORDER

PACK_PATH = Path(__file__).resolve().parents[1] / "packs" / "in" / "pack.yaml"


def _run() -> tuple[Report, list[EvalCase]]:
    from gatehouse.packs.loader import load_pack
    from gatehouse.rules.classifier import classify_text

    cases = generate_mini_set()
    pack = load_pack(PACK_PATH)
    preds = [classify_text(case.text, pack).score >= 0.70 for case in cases]
    return build_report(cases, preds, list(STRATA_ORDER)), cases


class TestWilson:
    def test_zero_total(self) -> None:
        assert wilson_interval(0, 0) == (0.0, 0.0)

    def test_all_success(self) -> None:
        lo, hi = wilson_interval(10, 10)
        assert lo > 0.70  # not overconfident at small n
        assert hi <= 1.0 and hi > 0.99  # clamped high, honest low

    def test_all_failure(self) -> None:
        lo, hi = wilson_interval(0, 10)
        assert lo == 0.0
        assert hi < 0.30

    def test_fifty_fifty_symmetric(self) -> None:
        lo, hi = wilson_interval(50, 100)
        assert abs((lo + hi) / 2 - 0.5) < 0.01
        assert lo < 0.5 < hi


class TestGenerator:
    def test_thirty_cases(self) -> None:
        cases = generate_mini_set()
        assert len(cases) == MINI_SET_SIZE

    def test_byte_identical_under_seed(self) -> None:
        a = [c.model_dump() for c in generate_mini_set(42)]
        b = [c.model_dump() for c in generate_mini_set(42)]
        assert a == b

    def test_both_classes_present(self) -> None:
        cases = generate_mini_set()
        truths = {c.ground_truth for c in cases}
        assert truths == {"scam", "benign"}

    def test_hard_trap_present(self) -> None:
        cases = generate_mini_set()
        traps = [c for c in cases if c.stratum == "govt_legit_trap"]
        assert len(traps) == 1 and traps[0].ground_truth == "benign"


class TestReport:
    def _run(self) -> tuple[Report, list[EvalCase]]:
        from gatehouse.packs.loader import load_pack
        from gatehouse.rules.classifier import classify_text

        cases = generate_mini_set()
        pack = load_pack(PACK_PATH)
        preds = [classify_text(case.text, pack).score >= 0.70 for case in cases]
        return build_report(cases, preds, list(STRATA_ORDER)), cases

    def test_confusion_sums_to_n(self) -> None:
        report, cases = self._run()
        assert report.tp + report.fp + report.tn + report.fn == len(cases)

    def test_intervals_bracket_point_estimates(self) -> None:
        report, _cases = self._run()
        if report.precision > 0:  # interval defined only when denominator nonzero
            assert report.precision_ci[0] <= report.precision <= report.precision_ci[1]
        if (report.tp + report.fn) > 0:
            assert report.recall_ci[0] <= report.recall <= report.recall_ci[1]

    def test_length_mismatch_raises(self) -> None:
        cases = generate_mini_set()[:5]
        with pytest.raises(ValueError, match="predictions"):
            build_report(cases, [True], [])

    def test_per_stratum_ordered_and_complete(self) -> None:
        from gatehouse.packs.schemas import STRATA_ORDER

        report, _cases = self._run()
        names = [s.stratum for s in report.per_stratum]
        expected = [s for s in STRATA_ORDER if s in set(names)]
        assert names == expected  # canonical doc order, byte-stable reports
        assert sum(s.n for s in report.per_stratum) == report.cases


class TestFalseSilence:
    """Doc 19 section 3: the silenced-benign rate rides beside the false-gate rate."""

    def _cases(self) -> list[EvalCase]:
        return [
            EvalCase(
                id=f"c{i}",
                stratum=STRATA_ORDER[0],
                lang="en",
                difficulty="easy",
                ground_truth=truth,
                text="t",
            )
            for i, truth in enumerate(["benign", "benign", "scam"])
        ]

    def test_unmeasured_is_none_not_zero(self) -> None:
        """A run without bands must not claim a clean sheet it never checked."""
        cases = self._cases()
        report = build_report(cases, [False, False, True], list(STRATA_ORDER))
        assert report.false_silence_rate is None
        assert report.silenced_benign == 0

    def test_clean_run_measures_zero(self) -> None:
        cases = self._cases()
        report = build_report(
            cases,
            [False, False, True],
            list(STRATA_ORDER),
            silence_bands=["PASS", "PASS", "SILENT_KILL"],
        )
        assert report.false_silence_rate == 0.0
        assert report.silenced_benign == 0

    def test_silenced_benign_case_is_counted(self) -> None:
        """One of two benign cases silenced is a 50 percent false-silence rate."""
        cases = self._cases()
        report = build_report(
            cases,
            [True, False, True],
            list(STRATA_ORDER),
            silence_bands=["SILENT_KILL", "PASS", "SILENT_KILL"],
        )
        assert report.silenced_benign == 1
        assert report.false_silence_rate == 0.5

    def test_benign_escalated_but_not_silenced_is_a_gate_not_a_silence(self) -> None:
        """A false gate that still reached a human is not a false silence."""
        cases = self._cases()
        report = build_report(
            cases,
            [True, False, True],
            list(STRATA_ORDER),
            silence_bands=["AGENT_SCREEN", "PASS", "SILENT_KILL"],
        )
        assert report.false_gate_rate == 0.5
        assert report.false_silence_rate == 0.0

    def test_band_length_mismatch_is_refused(self) -> None:
        cases = self._cases()
        with pytest.raises(ValueError, match="bands="):
            build_report(cases, [False, False, True], list(STRATA_ORDER), silence_bands=["PASS"])
