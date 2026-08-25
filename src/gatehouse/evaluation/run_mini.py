"""Offline eval runner: mini-set through the rule classifier.

Usage:
    python -m gatehouse.evaluation.run_mini            # human report to stdout
    python -m gatehouse.evaluation.run_mini --json out # machine metrics.json

Determinism contract: same seed and pack produce byte-identical JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from gatehouse.constants import SCORE_SCREEN
from gatehouse.evaluation.generator import generate_mini_set
from gatehouse.evaluation.metrics import build_report
from gatehouse.packs.schemas import STRATA_ORDER
from gatehouse.rules.classifier import classify_text


def run(pack_path: Path, threshold: float = SCORE_SCREEN) -> dict[str, Any]:
    """Run the mini set through the rule classifier at the given score threshold.

    Default operating point is SCORE_SCREEN (0.40): in P1 the rule engine IS
    the entire brain, so anything reaching the SCREEN band counts as flagged.
    The DECISION band (0.70) becomes the right threshold only in P2+ when the
    full agent pipeline exists and escalation cost matters.
    """
    from gatehouse.packs.loader import load_pack  # local import keeps --help cheap

    pack = load_pack(pack_path)
    cases = generate_mini_set()
    predictions = [classify_text(case.text, pack).score >= threshold for case in cases]
    report = build_report(cases, predictions, list(STRATA_ORDER))
    payload: dict[str, Any] = {
        "runner": "mini-rule-v0",
        "seed": 42,
        "pack_version": pack.version,
        "threshold_score": threshold,
        **report.model_dump(),
    }
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the P1 mini evaluation")
    parser.add_argument("--pack", type=Path, default=Path("packs/in/pack.yaml"))
    parser.add_argument("--json", type=Path, default=None, help="write metrics JSON here")
    args = parser.parse_args(argv)

    payload = run(args.pack)
    lines = [
        f"Gatehouse mini eval | pack v{payload['pack_version']} | seed {payload['seed']}",
        f"cases={payload['cases']} tp={payload['tp']} fp={payload['fp']} "
        f"tn={payload['tn']} fn={payload['fn']}",
        f"precision={payload['precision']} CI{payload['precision_ci']}",
        f"recall   ={payload['recall']} CI{payload['recall_ci']}",
        f"false_gate_rate={payload['false_gate_rate']}",
        "",
        "per stratum:",
    ]
    for s in payload["per_stratum"]:
        lines.append(
            f"  {s['stratum']:<18} n={s['n']:>2} tp={s['tp']} fp={s['fp']} "
            f"tn={s['tn']} fn={s['fn']}"
        )
    print("\n".join(lines))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\nmetrics written: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
