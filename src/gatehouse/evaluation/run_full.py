"""Full-set evaluation runner (doc 07 sections 2.1 and 4).

Runs a benchmark split through the REAL pipeline (orchestrator.investigate)
in one of two modes sharing identical scoring policy:

- LOCAL_MOCK (default): model=None so triage bands the deterministic rule
  score; in-memory graph, zero network, zero spend. Byte-stable payload.
- STAGING: the configured Bedrock model answers triage exactly as production
  would, against reserved-domain synthetic content only. Hard caps bound the
  whole run (max USD and max calls on ONE shared SpendMeter, so the existing
  chaos-tested breaker semantics apply across cases); every miss is exported
  with its artifacts so the failure taxonomy is written from real misses,
  never invented ones.

Both modes ride the same verdict-to-label mapping:
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
import time
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
from gatehouse.spend import SpendMeter

RUNNER_ID = "full-pipeline-local-mock-v1"
RUNNER_STAGING_ID = "full-pipeline-staging-v1"

# Charter section 8: eval runs are capped and seeded. These defaults bind a
# whole staging sweep to at most the soft development budget; explicit CLI
# values tighten them further. The shared meter is what enforces both.
DEFAULT_RUNNER_MAX_USD = 20.0
DEFAULT_RUNNER_MAX_CALLS = 5000

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


def _p_nearest(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile, empty-safe; deterministic."""
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, round(fraction * len(ordered)))
    return round(ordered[idx], 4)


def _stratified_subsample(cases: list[EvalCase], max_n: int) -> list[EvalCase]:
    """Deterministic stratum-proportional subsample of exactly max_n cases.

    Allocation is largest-remainder over the doc 07 strata so no family of
    scams vanishes from a capped run; stride selection keeps every template
    variant a chance to appear.
    """
    if max_n >= len(cases):
        return list(cases)
    groups: dict[str, list[int]] = {}
    for i, case in enumerate(cases):
        groups.setdefault(case.stratum, []).append(i)
    strata = [s for s in STRATA_ORDER if s in groups]
    raw = {s: len(groups[s]) * max_n / len(cases) for s in strata}
    alloc = {s: int(raw[s]) for s in strata}
    remaining = max_n - sum(alloc.values())
    order = sorted(strata, key=lambda s: (-(raw[s] - alloc[s]), strata.index(s)))
    cursor = 0
    while remaining > 0 and any(alloc[s] < len(groups[s]) for s in strata):
        s = order[cursor % len(order)]
        if alloc[s] < len(groups[s]):
            alloc[s] += 1
            remaining -= 1
        cursor += 1
    keep: set[int] = set()
    for s in strata:
        g = groups[s]
        take = alloc[s]
        step = len(g) / take if take else 0.0
        keep.update(g[round(k * step)] for k in range(take))
    return [c for i, c in enumerate(cases) if i in keep]


async def _run_cases(
    cases: list[EvalCase],
    pack: CountryPack,
    settings: Settings,
    model: Any = None,
    meter: SpendMeter | None = None,
    quiet: bool = False,
) -> tuple[list[CaseResult], list[float]]:
    """Replay every case through the full pipeline; fresh graph per case.

    Returns results with their runner-side wall milliseconds (the product
    latency metric is measured on the live webhook leg, never here).
    """
    results: list[CaseResult] = []
    walls: list[float] = []
    total = len(cases)
    started = time.perf_counter()
    for n, case in enumerate(cases, start=1):
        t0 = time.perf_counter()
        result = await investigate(
            case_id=case.id,
            raw_text=case.text,
            pack=pack,
            store=InMemoryGraphStore(),
            settings=settings,
            model=model,
            meter=meter,
        )
        walls.append(round((time.perf_counter() - t0) * 1000, 2))
        results.append(result)
        if not quiet and (n % 25 == 0 or n == total):
            spend = meter.total_usd if meter is not None else 0.0
            calls = meter.total_calls if meter is not None else 0
            elapsed = time.perf_counter() - started
            print(
                f"[eval] {n}/{total} cases | wall {elapsed:.1f}s | "
                f"model calls {calls} | est spend ${spend:.4f}",
                flush=True,
            )
    return results, walls


def run_split(
    pack_path: Path,
    split: str,
    screen_floor: float,
    reason: str = "",
    mode: str = "local_mock",
    max_cases: int | None = None,
    max_usd_cap: float | None = None,
    max_calls_cap: int | None = None,
    model_override: Any = None,
    quiet: bool = False,
) -> dict[str, Any]:
    """Run one split end to end and return the byte-stable payload."""
    if mode not in ("local_mock", "staging"):
        raise ValueError(f"unknown mode: {mode}")
    pack = load_pack(pack_path)
    settings = Settings(rule_screen_floor=screen_floor)

    model_id_note = "local_mock_rules"
    model: Any = None
    meter: SpendMeter | None = None
    requested_cases: int | None = None
    if mode == "staging":
        if model_override is not None:
            model = model_override
        else:
            # The environment gate inside build_model is bypassed on purpose:
            # staging evaluation is an explicit operator action from this CLI,
            # so the setting that gates production wiring must not gate it.
            from strands.models import BedrockModel

            model = BedrockModel(model_id=settings.bedrock_model_id, region_name=settings.region)
        cfg = model.get_config() if hasattr(model, "get_config") else {}
        model_id_note = str(cfg.get("model_id", "bedrock"))
        meter = SpendMeter(
            max_usd=max_usd_cap if max_usd_cap is not None else DEFAULT_RUNNER_MAX_USD,
            max_calls=max_calls_cap if max_calls_cap is not None else DEFAULT_RUNNER_MAX_CALLS,
        )

    if split == "dev":
        cases = generate_dev_set()
        seed = DEV_SEED
    elif split == "holdout":
        cases = generate_holdout_set()
        seed = HOLDOUT_SEED
    else:
        raise ValueError(f"unknown split: {split}")
    if max_cases is not None and max_cases < len(cases):
        requested_cases = len(cases)
        cases = _stratified_subsample(cases, max_cases)

    results, walls = asyncio.run(_run_cases(cases, pack, settings, model, meter, quiet))
    predictions = [_flagged(r) for r in results]
    report = build_report(cases, predictions, list(STRATA_ORDER))

    taxonomy: Counter[str] = Counter()
    miss_ledger: list[dict[str, Any]] = []
    for case, result, pred in zip(cases, results, predictions, strict=True):
        actual = case.ground_truth == "scam"
        if actual != pred:
            taxonomy[_classify_miss(case, result)] += 1
            miss_ledger.append(
                {
                    "case_id": case.id,
                    "stratum": case.stratum,
                    "ground_truth": case.ground_truth,
                    "verdict": result.verdict,
                    "triage_class": result.triage_class,
                    "confidence": result.triage_confidence,
                    "reason_codes": list(result.reason_codes),
                    "degraded_flags": list(result.degraded_flags),
                    "flagged_would_interrupt": pred,
                    "taxonomy_class": _classify_miss(case, result),
                }
            )

    degraded_share = (
        round(sum(1 for r in results if r.degraded_flags) / len(results), 4) if results else 0.0
    )
    refusals = sum(1 for r in results if "TRIAGE_BUDGET_REFUSED" in r.degraded_flags)
    spends = [r.spend_usd for r in results]

    payload: dict[str, Any] = {
        "runner": RUNNER_ID,
        "split": split,
        "seed": seed,
        "screen_floor": screen_floor,
        "pack_version": pack.version,
        "pack_sha256": hashlib.sha256(pack_path.read_bytes()).hexdigest(),
        "model_mode": "local_mock_rules" if mode == "local_mock" else model_id_note,
        **report.model_dump(),
        "noise_leak_note": (
            "notification path not exercised in local_mock; rate not measurable here"
        ),
        "degraded_case_share": degraded_share,
        "failure_taxonomy": {cls: taxonomy.get(cls, 0) for cls in _TAXONOMY_CLASSES},
    }
    if mode == "staging":
        payload.update(
            {
                "runner": RUNNER_STAGING_ID,
                "noise_leak_note": (
                    "notification path not exercised by this runner; rate not measurable here"
                ),
                "model_id": model_id_note,
                "requested_cases": requested_cases if requested_cases is not None else len(cases),
                "ran_cases": len(results),
                "max_usd_cap": meter.max_usd if meter else None,
                "max_calls_cap": meter.max_calls if meter else None,
                "model_calls": meter.total_calls if meter else 0,
                "breaker_refusals": refusals,
                "runner_wall_ms_p50": _p_nearest(walls, 0.50),
                "runner_wall_ms_p95": _p_nearest(walls, 0.95),
                "spend_usd_total": meter.total_usd if meter else round(sum(spends), 6),
                "est_spend_mean_usd": round(sum(spends) / len(spends), 6) if spends else 0.0,
                "est_spend_p95_usd": _p_nearest(spends, 0.95),
                "misses": miss_ledger,
            }
        )
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
        "--model-mode",
        choices=["local_mock", "staging"],
        default="local_mock",
        help="staging answers triage with the real configured Bedrock model, hard-capped",
    )
    parser.add_argument(
        "--screen-floor", type=float, default=None, help="override calibrated floor"
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="stratum-proportional deterministic subsample size",
    )
    parser.add_argument(
        "--max-usd-cap",
        type=float,
        default=None,
        help="whole-run spend ceiling enforced by the shared breaker (default 20.0)",
    )
    parser.add_argument(
        "--max-calls-cap",
        type=int,
        default=None,
        help="whole-run model-call ceiling enforced by the shared breaker (default 5000)",
    )
    parser.add_argument("--json", type=Path, default=None, help="write metrics JSON here")
    parser.add_argument("--quiet", action="store_true", help="suppress progress lines")
    parser.add_argument("--confirm-holdout", action="store_true", help="required for holdout split")
    parser.add_argument("--reason", type=str, default="", help="why the hold-out is opening")
    args = parser.parse_args(argv)

    if args.split == "holdout" and not (args.confirm_holdout and args.reason.strip()):
        parser.error("holdout split requires --confirm-holdout AND a non-empty --reason")

    floor = Settings().rule_screen_floor if args.screen_floor is None else args.screen_floor
    try:
        payload = run_split(
            args.pack,
            args.split,
            floor,
            reason=args.reason,
            mode=args.model_mode,
            max_cases=args.max_cases,
            max_usd_cap=args.max_usd_cap,
            max_calls_cap=args.max_calls_cap,
            quiet=args.quiet,
        )
    except ValueError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2

    lines = [
        f"Gatehouse full eval | split={payload['split']} | pack v{payload['pack_version']} "
        f"| seed {payload['seed']} | floor {payload['screen_floor']}",
        f"cases={payload['cases']} tp={payload['tp']} fp={payload['fp']} "
        f"tn={payload['tn']} fn={payload['fn']}",
        f"precision={payload['precision']} CI{payload['precision_ci']}",
        f"recall   ={payload['recall']} CI{payload['recall_ci']}",
        f"false_gate_rate={payload['false_gate_rate']}"
        f" degraded_share={payload['degraded_case_share']}",
    ]
    if args.model_mode == "staging":
        lines.append(
            f"model={payload['model_id']} | calls {payload['model_calls']} "
            f"| est spend ${payload['spend_usd_total']:.4f} "
            f"| breaker refusals {payload['breaker_refusals']} "
            f"| wall p50/p95 ms {payload['runner_wall_ms_p50']}/{payload['runner_wall_ms_p95']}"
        )
    lines += [
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
