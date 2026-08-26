"""Calibration selection-rule tests: fixed contract, published pre/post."""

from __future__ import annotations

from gatehouse.evaluation.calibrate import BASELINE_FLOOR, RECALL_TARGET, _select


def _point(floor: float, recall: float, fgr: float, precision: float = 1.0) -> dict[str, float]:
    return {
        "screen_floor": floor,
        "precision": precision,
        "recall": recall,
        "false_gate_rate": fgr,
        "tp": 0,
        "fp": 0,
        "tn": 0,
        "fn": 0,
    }


class TestSelectionRule:
    def test_prefers_lowest_false_gate_among_eligible(self) -> None:
        points = [_point(0.30, RECALL_TARGET, 0.02), _point(0.40, RECALL_TARGET, 0.01)]
        assert _select(points)["screen_floor"] == 0.40

    def test_ignores_points_below_recall_target(self) -> None:
        points = [
            _point(0.60, 0.60, 0.0),  # perfect false-gate, fails recall bar
            _point(0.40, RECALL_TARGET, 0.03),
        ]
        assert _select(points)["screen_floor"] == 0.40

    def test_ties_resolve_toward_baseline_not_extremes(self) -> None:
        points = [
            _point(0.25, 1.0, 0.0),
            _point(BASELINE_FLOOR, 1.0, 0.0),
            _point(0.45, 1.0, 0.0),
        ]
        assert _select(points)["screen_floor"] == BASELINE_FLOOR

    def test_precision_breaks_false_gate_ties(self) -> None:
        points = [
            _point(0.35, RECALL_TARGET, 0.01, precision=0.97),
            _point(0.40, RECALL_TARGET, 0.01, precision=0.99),
        ]
        assert _select(points)["screen_floor"] == 0.40

    def test_no_eligible_point_still_returns_recommendation(self) -> None:
        points = [_point(0.55, 0.70, 0.0), _point(0.60, 0.62, 0.0)]
        best = _select(points)
        assert best["recall"] == max(p["recall"] for p in points)
