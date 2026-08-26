"""Threshold calibration on the DEV split only (doc 07 section 6).

Sweeps the calibrated SCREEN floor across a fixed grid, running each point
through the full LOCAL_MOCK pipeline over the 480-case dev set. Selection
rule, fixed before looking at results: minimize false-gate rate subject to
recall >= the published v1 bar (0.85); ties break toward higher precision,
then toward the LOWER floor (catch more scams at equal measured quality).

Discipline:
- dev split only; this module never imports the hold-out generator;
- pre/post both published: the baseline floor (0.40) metrics appear beside
  the recommendation so the delta is visible, never hidden;
- applying the winner is an explicit act: GATEHOUSE_RULE_SCREEN_FLOOR in the
  environment, or --screen-floor on eval commands. Nothing auto-edits config.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from gatehouse.evaluation.run_full import run_split
from gatehouse.packs.loader import PackError, load_pack
from gatehouse.packs.schemas import CountryPack

GRID: tuple[float, ...] = (0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60)
RECALL_TARGET = 0.85
BASELINE_FLOOR = 0.40


def _select(points: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply the fixed selection rule to swept operating points.

    Ties resolve toward the baseline floor: moving the operating point is a
    cost (behavior change, re-disclosure, drift risk) and must be paid only
    for measured gain, never for an equal-metric grid neighbor.
    """
    eligible = [p for p in points if p["recall"] >= RECALL_TARGET]
    pool = eligible if eligible else points
    best = min(
        pool,
        key=lambda p: (
            p["false_gate_rate"],
            -p["precision"],
            abs(p["screen_floor"] - BASELINE_FLOOR),
        ),
    )
    return best


def calibrate(pack_path: Path) -> dict[str, Any]:
    """Sweep the grid on dev, select the operating point, publish pre/post."""
    pack: CountryPack = load_pack(pack_path)  # fail fast before spending cycles

    baseline = run_split(pack_path, "dev", BASELINE_FLOOR)
    points: list[dict[str, Any]] = []
    for floor in GRID:
        result = run_split(pack_path, "dev", floor)
        points.append(
            {
                "screen_floor": floor,
                "precision": result["precision"],
                "recall": result["recall"],
                "false_gate_rate": result["false_gate_rate"],
                "tp": result["tp"],
                "fp": result["fp"],
                "tn": result["tn"],
                "fn": result["fn"],
            }
        )

    best = _select(points)
    meets_target = best["recall"] >= RECALL_TARGET
    payload: dict[str, Any] = {
        "runner": "calibration-dev-sweep-v1",
        "pack_version": pack.version,
        "grid": list(GRID),
        "recall_target": RECALL_TARGET,
        "baseline": {
            "screen_floor": BASELINE_FLOOR,
            "precision": baseline["precision"],
            "recall": baseline["recall"],
            "false_gate_rate": baseline["false_gate_rate"],
        },
        "points": points,
        "recommended_floor": best["screen_floor"],
        "meets_recall_target": meets_target,
        "rationale": (
            "min false-gate subject to recall>=target; ties: higher precision, then closest to "
            "the 0.40 baseline (no operating-point change without measured gain)"
            if eligible_count(points)
            else (
                "NO point met the recall target; recommendation maximizes recall instead "
                "and the gap is recorded honestly"
            )
        ),
    }
    return payload


def eligible_count(points: list[dict[str, Any]]) -> bool:
    """True when at least one swept point reaches the recall target."""
    return any(p["recall"] >= RECALL_TARGET for p in points)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calibrate the SCREEN floor on the dev split")
    parser.add_argument("--pack", type=Path, default=Path("packs/in/pack.yaml"))
    parser.add_argument("--json", type=Path, default=None, help="write calibration JSON here")
    args = parser.parse_args(argv)

    try:
        payload = calibrate(args.pack)
    except PackError as exc:
        print(f"pack error: {exc}", file=sys.stderr)
        return 1

    lines = [
        "Threshold calibration | dev split only | pack v" + payload["pack_version"],
        f"{'floor':>6} {'precision':>9} {'recall':>8} {'false_gate':>10}",
    ]
    for p in payload["points"]:
        marker = " <-- baseline" if p["screen_floor"] == BASELINE_FLOOR else ""
        star = " * recommended" if p["screen_floor"] == payload["recommended_floor"] else ""
        lines.append(
            f"{p['screen_floor']:>6} {p['precision']:>9} {p['recall']:>8} "
            f"{p['false_gate_rate']:>10}{marker}{star}"
        )
    lines.append("")
    lines.append(f"recommended floor: {payload['recommended_floor']} ({payload['rationale']})")
    lines.append(
        "apply with: GATEHOUSE_RULE_SCREEN_FLOOR="
        f"{payload['recommended_floor']} (env) or --screen-floor on eval runs"
    )
    print("\n".join(lines))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\ncalibration written: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
