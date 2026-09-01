"""Weekly soak report (doc 07 section 2.2, acceptance criterion 4).

Pure aggregation over persisted case records: volume, verdict distribution,
escalation rate, degraded-mode share, spend stats, latency percentiles when
timestamps exist, guardian overrides when an override ledger feeds them in.
No AWS access here: `scripts/soak_fetch.py` pulls the raw items, this module
computes, `render_markdown` publishes. That split keeps the math testable
offline forever.

The quiet-week flag is the product's core promise made checkable: zero
guardian interruptions in a week where real volume was screened.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from gatehouse.constants import BAND_PASS, BAND_SILENT_KILL

SECONDS_PER_DAY = 86400
DEFAULT_WINDOW_DAYS = 7


class CaseRecord(BaseModel):
    """One persisted case item, channel-agnostic."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    household_id: str
    created_at: int
    verdict: str
    triage_class: str
    reason_codes: list[str] = Field(default_factory=list)
    spend_usd: float = 0.0
    degraded_flags: list[str] = Field(default_factory=list)
    forward_ms: float | None = None
    guardian_override: bool | None = None
    # Doc 19 section 3. None for cases persisted before the band existed, so
    # the report can say "unbanded" instead of silently counting them as PASS.
    silence_band: str | None = None


class WeeklySoakReport(BaseModel):
    """Aggregated honesty snapshot for one week of soak operation."""

    model_config = ConfigDict(extra="forbid")

    window_days: int
    window_start: int
    window_end: int
    cases: int
    verdict_counts: dict[str, int]
    triage_counts: dict[str, int]
    escalations: int
    escalation_rate: float
    degraded_case_share: float
    spend_total_usd: float
    spend_mean_usd: float
    spend_p95_usd: float
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    guardian_overrides: int
    override_ledger_present: bool
    quiet_week: bool
    # The silence ledger: how much of the week the household never had to see.
    band_counts: dict[str, int]
    silent_kills: int
    undisturbed_share: float
    unbanded_cases: int


def _percentile(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile; deterministic, empty-safe."""
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, round(fraction * len(ordered)))
    return round(ordered[idx], 4)


def _counts(values: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in sorted(set(values)):
        out[value] = values.count(value)
    return out


def build_weekly_report(
    records: list[CaseRecord],
    window_start: int,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> WeeklySoakReport:
    """Aggregate records whose created_at falls in [start, start + days)."""
    window_end = window_start + window_days * SECONDS_PER_DAY
    in_window = [r for r in records if window_start <= r.created_at < window_end]

    verdicts = [r.verdict for r in in_window]
    triages = [r.triage_class for r in in_window]
    escalations = sum(1 for v in verdicts if v in ("SUSPICIOUS", "SCAM"))
    degraded_share = (
        round(sum(1 for r in in_window if r.degraded_flags) / len(in_window), 4)
        if in_window
        else 0.0
    )
    spends = [r.spend_usd for r in in_window]
    latencies = [r.forward_ms for r in in_window if r.forward_ms is not None]
    overrides = [r for r in in_window if r.guardian_override is not None and r.guardian_override]
    any_ledger_signal = any(r.guardian_override is not None for r in in_window)

    # Silence ledger. Cases predating the band carry None and are reported as
    # unbanded rather than folded into PASS: the undisturbed share is a claim
    # about what the household was spared, and it may only count cases that
    # actually recorded a band.
    banded = [r.silence_band for r in in_window if r.silence_band is not None]
    unbanded = len(in_window) - len(banded)
    silent_kills = sum(1 for b in banded if b == BAND_SILENT_KILL)
    undisturbed = sum(1 for b in banded if b in (BAND_SILENT_KILL, BAND_PASS))

    total_spend = round(sum(spends), 6)
    return WeeklySoakReport(
        window_days=window_days,
        window_start=window_start,
        window_end=window_end,
        cases=len(in_window),
        verdict_counts=_counts(verdicts),
        triage_counts=_counts(triages),
        escalations=escalations,
        escalation_rate=round(escalations / len(in_window), 4) if in_window else 0.0,
        degraded_case_share=degraded_share,
        spend_total_usd=total_spend,
        spend_mean_usd=round(total_spend / len(spends), 6) if spends else 0.0,
        spend_p95_usd=_percentile(spends, 0.95),
        latency_p50_ms=_percentile(latencies, 0.50) if latencies else None,
        latency_p95_ms=_percentile(latencies, 0.95) if latencies else None,
        guardian_overrides=len(overrides),
        override_ledger_present=any_ledger_signal,
        # bool(...) not just for typing: an empty window yields [], which
        # pydantic rejects on this strict bool field; empty is never quiet
        # anyway because no volume was screened to prove the value.
        quiet_week=bool(in_window) and escalations == 0,
        band_counts=_counts(banded),
        silent_kills=silent_kills,
        undisturbed_share=round(undisturbed / len(banded), 4) if banded else 0.0,
        unbanded_cases=unbanded,
    )


def render_markdown(report: WeeklySoakReport) -> str:
    """Human-readable weekly report; committed under docs/eval-results/."""
    lines = [
        "# Soak Week Report",
        "",
        f"Window: {report.window_days} days "
        f"({report.window_start} .. {report.window_end}, epoch seconds)",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Cases screened | {report.cases} |",
        f"| Escalations (SUSPICIOUS+SCAM) | {report.escalations} ({report.escalation_rate}) |",
        f"| Quiet week | {'yes' if report.quiet_week else 'no'} |",
        f"| Silent kills (never paged a human) | {report.silent_kills} |",
        f"| Undisturbed share | {report.undisturbed_share} |",
        f"| Unbanded cases (predate the band) | {report.unbanded_cases} |",
        f"| Degraded-case share | {report.degraded_case_share} |",
        f"| Spend total / mean / p95 USD | {report.spend_total_usd} / "
        f"{report.spend_mean_usd} / {report.spend_p95_usd} |",
        f"| Latency p50/p95 ms | {report.latency_p50_ms} / {report.latency_p95_ms} |",
        "",
        "Verdict distribution:",
        "",
        "| Verdict | Count |",
        "|---|---|",
    ]
    for verdict in sorted(report.verdict_counts):
        lines.append(f"| {verdict} | {report.verdict_counts[verdict]} |")
    lines += ["", "Triage distribution:", "", "| Class | Count |", "|---|---|"]
    for cls in sorted(report.triage_counts):
        lines.append(f"| {cls} | {report.triage_counts[cls]} |")
    if report.override_ledger_present:
        lines += [
            "",
            f"Guardian overrides recorded: {report.guardian_overrides}",
        ]
    else:
        lines += [
            "",
            "Override ledger: not present yet; guardian agreement unmeasured this week.",
        ]
    return "\n".join(lines) + "\n"


def _record_from_item(item: dict[str, Any]) -> CaseRecord:
    """Adapt one DynamoDB-style item (attr maps) or plain dict into a record."""

    def plain(key: str, default: Any = None) -> Any:
        value = item.get(key, default)
        if isinstance(value, dict) and set(value.keys()) == {"S"}:
            return value["S"]
        if isinstance(value, dict) and set(value.keys()) == {"N"}:
            return float(value["N"])
        if isinstance(value, dict) and set(value.keys()) == {"SS"}:
            return list(value["SS"])
        return value

    created = plain("created_at", 0)
    spend = plain("spend_usd", 0.0)
    reasons = plain("reason_codes", []) or []
    flags = plain("degraded_flags", []) or []
    return CaseRecord(
        case_id=str(plain("sk", plain("case_id", ""))).replace("CASE#", ""),
        household_id=str(plain("pk", "")).replace("HOUSEHOLD#", ""),
        created_at=int(created),
        verdict=str(plain("verdict", "")),
        triage_class=str(plain("triage_class", "")),
        reason_codes=[str(r) for r in reasons if r != "NONE"],
        spend_usd=float(spend),
        degraded_flags=[str(f) for f in flags if f != "NONE"],
        # Absent on rows written before the band shipped; stays None so the
        # report counts them as unbanded rather than inventing a PASS.
        silence_band=(str(band) if (band := plain("silence_band")) else None),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the weekly soak report")
    parser.add_argument("--records", type=Path, required=True, help="records JSON file")
    parser.add_argument("--days", type=int, default=DEFAULT_WINDOW_DAYS)
    parser.add_argument("--week-start", type=int, default=None, help="epoch seconds window start")
    parser.add_argument("--latest", action="store_true", help="window ends at newest record")
    parser.add_argument("--markdown", type=Path, default=None, help="also write markdown here")
    args = parser.parse_args(argv)

    raw = json.loads(args.records.read_text(encoding="utf-8"))
    records = [_record_from_item(item) for item in raw]
    if not records:
        print("no records supplied; nothing to report", file=sys.stderr)
        return 1
    newest = max(r.created_at for r in records)
    start = (
        args.week_start if args.week_start is not None else (newest - args.days * SECONDS_PER_DAY)
    )
    report = build_weekly_report(records, start, args.days)
    payload = json.dumps(report.model_dump(), indent=2, sort_keys=True)
    print(payload)
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(render_markdown(report), encoding="utf-8")
        print(f"\nmarkdown written: {args.markdown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
