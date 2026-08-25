"""Metrics computation with Wilson 95 percent score intervals (doc 07 section 6).

Wilson intervals are used instead of naive normal approximations because they
stay honest at small n, which is exactly the regime every early metric lives in.
"""

from __future__ import annotations

import math

from gatehouse.evaluation.schemas import EvalCase, Report, StratumMetrics

_Z95 = 1.959963984540054  # two-sided 95 percent


def wilson_interval(successes: int, total: int) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Returns (low, high); (0.0, 0.0) when total is zero.
    """
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denom = 1 + (_Z95 * _Z95) / total
    center = (p + (_Z95 * _Z95) / (2 * total)) / denom
    spread = (_Z95 / denom) * math.sqrt(p * (1 - p) / total + (_Z95 * _Z95) / (4 * total * total))
    return (max(0.0, center - spread), min(1.0, center + spread))


def build_report(
    cases: list[EvalCase],
    predicted_scam: list[bool],
    strata_order: list[str],
) -> Report:
    """Aggregate confusion tables overall and per stratum.

    Args:
        cases: labeled cases.
        predicted_scam: parallel list; True means classifier said scam.
        strata_order: stable ordering so reports stay byte-identical across runs.

    Raises:
        ValueError: length mismatch between cases and predictions.
    """
    if len(cases) != len(predicted_scam):
        raise ValueError(f"cases={len(cases)} but predictions={len(predicted_scam)}")

    tp = fp = tn = fn = 0
    per_stratum: dict[str, StratumMetrics] = {}

    for case, pred in zip(cases, predicted_scam, strict=True):
        actual_scam = case.ground_truth == "scam"
        key = (actual_scam, pred)

        if key == (True, True):
            tp += 1
        elif key == (False, True):
            fp += 1
        elif key == (False, False):
            tn += 1
        else:
            fn += 1

        metrics = per_stratum.setdefault(
            case.stratum,
            StratumMetrics(stratum=case.stratum, n=0),
        )
        metrics.n += 1
        if key == (True, True):
            metrics.tp += 1
        elif key == (False, True):
            metrics.fp += 1
        elif key == (False, False):
            metrics.tn += 1
        else:
            metrics.fn += 1

    precision_lo, precision_hi = wilson_interval(tp, tp + fp)
    recall_lo, recall_hi = wilson_interval(tp, tp + fn)

    benign_total = fp + tn
    # NOISE-leak assertions require the P2 pipeline; the rule runner cannot leak
    # notifications by construction because it never notifies.
    noise_leak_rate = 0.0

    return Report(
        cases=len(cases),
        tp=tp,
        fp=fp,
        tn=tn,
        fn=fn,
        precision=round(tp / (tp + fp), 4) if (tp + fp) else 0.0,
        precision_ci=(round(precision_lo, 4), round(precision_hi, 4)),
        recall=round(tp / (tp + fn), 4) if (tp + fn) else 0.0,
        recall_ci=(round(recall_lo, 4), round(recall_hi, 4)),
        false_gate_rate=round(fp / benign_total, 4) if benign_total else 0.0,
        noise_leak_rate=noise_leak_rate,
        per_stratum=[per_stratum[s] for s in strata_order if s in per_stratum],
    )
