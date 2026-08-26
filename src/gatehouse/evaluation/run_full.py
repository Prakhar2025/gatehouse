"""Full-set evaluation runner (doc 07 sections 2.1 and 4).

Runs a benchmark split through the REAL pipeline (orchestrator.investigate)
in LOCAL_MOCK mode: model=None so triage bands the deterministic rule score,
the graph store is in-memory, zero network, zero spend. This is the same code
path production runs minus the model leg, which is exactly what makes results
comparable when the STAGING runner arrives.

Verdict-to-label mapping (what would touch a human in production):
    flagged = verdict in {SUSPICIOUS, SCAM}
            or (NEEDS_HUMAN raised from a triage class of SCREEN or above)
A NEEDS_HUMAN caused purely by degraded infrastructure on a NOISE-class signal
does not interrupt anyone and therefore does not count as a flag.

Split gating: `--split dev` runs freely (all calibration happens there).
`--split holdout` is REFUSED unless `--confirm-holdout` is passed together
with `--reason`; the opening then embeds seed, pack version, floor, and reason
into the payload so every hold-out look is auditable forever.

Output JSON is byte-stable for fixed inputs (sorted keys, no timestamps), so
regression diffs are exact.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from gatehouse.config import Settings
from gatehouse.constants import (
    CLASS_DECISION,
    CLASS_EMERGENCY,
    CLASS_INFO,
    CLASS_NOISE,
    CLASS_SCREEN,
    VERDICT_NEEDS_HUMAN,
    VERDICT_SUSPICIOUS,
)
from gatehouse.evaluation.full_set import (
    DEV_SEED,
    HOLDOUT_SEED,
    generate_dev_set,
    generate_holdout_set,
)
from gatehouse.evaluation.metrics import build_report
from gatehouse.evaluation.schemas import EvalCase
from gatehouse.graph.store import InMemoryGraphStore
from gatehouse.orchestrator import CaseResult, investigate
from gatehouse.packs.loader import load_pack
from gatehouse.packs.schemas import STRATA_ORDER, CountryPack

RUNNER_ID = "full-pipeline-local-mock-v1"

# Explicit band rank: class-name string comparison would be alphabetical and
# therefore wrong ("DECISION" sorts below "SCREEN").
_BAND_RANK: dict[str, int] = {
    CLASS_NOISE: 0,
    CLASS_INFO: 1,
    CLASS_SCREEN: 2,
    CLASS_DECISION: 3,
    CLASS_EMERGENCY: 4,
}

_TAXONOMY_CLASSES = (
    "missed_pattern_family",
    "language_gap",
    "verification_tool_gap",
    "threshold_miscalibration",
    "orchestration_bug",
    "degraded_mode_cause",
    "labeling_dispute",
)


def _flagged(result: CaseResult) -> bool:
    """True when this verdict would have interrupted a member."""
    if result.verdict in (VERDICT_SUSPICIOUS, "SCAM"):
        return True
    if result.verdict == VERDICT_NEEDS_HUMAN:
        return _BAND_RANK.get(result.triage_class, 0) >= _BAND_RANK[CLASS_SCREEN]
    return False


def _classify_miss(case: EvalCase, result: CaseResult) -> str:
    """Failure-taxonomy class for one miss (doc 07 section 5).

    Deterministic from the case label and the case's own artifacts; no
    invented humility, no hidden failures.
    """
    actual_scam = case.ground_truth == "scam"
    predicted = _flagged(result)
    if actual_scam and not predicted:
        if result.degraded_flags:
            return "degraded_mode_cause"
        # Triage saw it but policy let it go, versus nothing matched at all.
        if _BAND_RANK.get(result.triage_class, 0) >= _BAND_RANK[CLASS_SCREEN]:
            return "orchestration_bug"
        rule_score = result.triage_confidence
        if rule_score <= 0.0:
            return "missed_pattern_family"
        return "threshold_miscalibration"
    if not actual_scam and predicted:
        reasons = set(result.reason_codes)
        if "DOMAIN_UNVERIFIED" in reasons:
            return "verification_tool_gap"
        if result.degraded_flags:
            return "degraded_mode_cause"
        return "threshold_miscalibration"
    return "labeling_dispute"


async def _run_cases(
    cases: list[EvalCase],
    pack: CountryPack,
    settings: Settings,
) -> list[CaseResult]:
    """Replay every case through the full pipeline; fresh graph per case."""
    results: list[CaseResult] = []
    for case in cases:
        result = await investigate(
            case_id=case.id,
            raw_text=case.text,
            pack=pack,
            store=InMemoryGraphStore(),
            settings=settings,
            model=None,
        )
        results.append(result)
    return results


def run_split(
    pack_path: Path,
    split: str,
    screen_floor: float,
    reason: str = "",
) -> dict[str, Any]:
    """Run one split end to end and return the byte-stable payload."""
    pack = load_pack(pack_path)
    settings = Settings(rule_screen_floor=screen_floor)
    if split == "dev":
        cases = generate_dev_set()
        seed = DEV_SEED
    elif split == "holdout":
        cases = generate_holdout_set()
        seed = HOLDOUT_SEED
    else:
        raise ValueError(f"unknown split: {split}")

    results = asyncio.run(_run_cases(cases, pack, settings))
    predictions = [_flagged(r) for r in results]
    report = build_report(cases, predictions, list(STRATA_ORDER))

    taxonomy: Counter[str] = Counter()
    for case, result, pred in zip(cases, results, predictions, strict=True):
        actual = case.ground_truth == "scam"
        if actual != pred:
            taxonomy[_classify_miss(case, result)] += 1

    degraded_share = (
        round(sum(1 for r in results if r.degraded_flags) / len(results), 4) if results else 0.0
    )

    payload: dict[str, Any] = {
        "runner": RUNNER_ID,
        "split": split,
        "seed": seed,
        "screen_floor": screen_floor,
        "pack_version": pack.version,
        "pack_sha256": hashlib.sha256(pack_path.read_bytes()).hexdigest(),
        "model_mode": "local_mock_rules",
        **report.model_dump(),
        "noise_leak_note": (
            "notification path not exercised in local_mock; rate not measurable here"
        ),
        "degraded_case_share": degraded_share,
        "failure_taxonomy": {cls: taxonomy.get(cls, 0) for cls in _TAXONOMY_CLASSES},
    }
    if split == "holdout":
        payload["holdout_opening"] = {
            "confirmed": True,
            "reason": reason,
            "opening_number": "recorded_by_owner",
        }
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Full-set evaluation through the real pipeline")
    parser.add_argument("--pack", type=Path, default=Path("packs/in/pack.yaml"))
    parser.add_argument("--split", choices=["dev", "holdout"], default="dev")
    parser.add_argument(
        "--screen-floor", type=float, default=None, help="override calibrated floor"
    )
    parser.add_argument("--json", type=Path, default=None, help="write metrics JSON here")
    parser.add_argument("--confirm-holdout", action="store_true", help="required for holdout split")
    parser.add_argument("--reason", type=str, default="", help="why the hold-out is opening")
    args = parser.parse_args(argv)

    if args.split == "holdout" and not (args.confirm_holdout and args.reason.strip()):
        parser.error("holdout split requires --confirm-holdout AND a non-empty --reason")

    floor = Settings().rule_screen_floor if args.screen_floor is None else args.screen_floor
    payload = run_split(args.pack, args.split, floor, reason=args.reason)

    lines = [
        f"Gatehouse full eval | split={payload['split']} | pack v{payload['pack_version']} "
        f"| seed {payload['seed']} | floor {payload['screen_floor']}",
        f"cases={payload['cases']} tp={payload['tp']} fp={payload['fp']} "
        f"tn={payload['tn']} fn={payload['fn']}",
        f"precision={payload['precision']} CI{payload['precision_ci']}",
        f"recall   ={payload['recall']} CI{payload['recall_ci']}",
        f"false_gate_rate={payload['false_gate_rate']}"
        f" degraded_share={payload['degraded_case_share']}",
        "",
        "per stratum:",
    ]
    for s in payload["per_stratum"]:
        lines.append(
            f"  {s['stratum']:<24} n={s['n']:>3} tp={s['tp']:>3} fp={s['fp']:>3} "
            f"tn={s['tn']:>3} fn={s['fn']:>3}"
        )
    misses = {k: v for k, v in payload["failure_taxonomy"].items() if v}
    lines.append("")
    lines.append(f"failure taxonomy: {misses if misses else 'no misses'}")
    print("\n".join(lines))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\nmetrics written: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
