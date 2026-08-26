"""Weekly soak report: windows, quiet-week flag, adapters, rendering."""

from __future__ import annotations

from gatehouse.evaluation.soak import (
    SECONDS_PER_DAY,
    CaseRecord,
    _record_from_item,
    build_weekly_report,
    render_markdown,
)

T0 = 1_800_000_000


def _rec(
    case_id: str,
    created: int,
    verdict: str = "SAFE",
    triage: str = "NOISE",
    degraded: tuple[str, ...] = (),
    spend: float = 0.001,
    override: bool | None = None,
    household: str = "fam-1",
) -> CaseRecord:
    return CaseRecord(
        case_id=case_id,
        household_id=household,
        created_at=created,
        verdict=verdict,
        triage_class=triage,
        spend_usd=spend,
        degraded_flags=list(degraded),
        guardian_override=override,
    )


class TestWindowing:
    def test_only_records_inside_window_count(self) -> None:
        records = [
            _rec("before", T0 - 10),
            _rec("inside-early", T0 + 5),
            _rec("inside-late", T0 + SECONDS_PER_DAY * 7 - 1),
            _rec("after", T0 + SECONDS_PER_DAY * 7),
        ]
        report = build_weekly_report(records, T0)
        assert report.cases == 2
        assert report.window_end == T0 + 7 * SECONDS_PER_DAY

    def test_empty_window_is_all_zeroes_not_crash(self) -> None:
        report = build_weekly_report([_rec("old", T0 - 100)], T0)
        assert report.cases == 0
        assert report.quiet_week is False
        assert report.spend_total_usd == 0.0


class TestQuietWeekAndEscalation:
    def test_quiet_week_true_when_zero_escalations_with_volume(self) -> None:
        records = [_rec(f"c{i}", T0 + i) for i in range(4)]
        assert build_weekly_report(records, T0).quiet_week is True

    def test_scam_or_suspicious_counts_as_escalation(self) -> None:
        records = [
            _rec("a", T0, verdict="SCAM"),
            _rec("b", T0 + 1, verdict="SUSPICIOUS"),
            _rec("c", T0 + 2),
        ]
        report = build_weekly_report(records, T0)
        assert report.escalations == 2
        assert report.quiet_week is False
        assert report.escalation_rate == round(2 / 3, 4)

    def test_needs_human_is_not_an_escalation_but_degraded_share_rises(self) -> None:
        records = [
            _rec("a", T0, verdict="NEEDS_HUMAN", degraded=("VERIFY_UNAVAILABLE",)),
            _rec("b", T0 + 1),
        ]
        report = build_weekly_report(records, T0)
        assert report.escalations == 0
        assert report.degraded_case_share == 0.5


class TestSpendAndLatency:
    def test_spend_stats(self) -> None:
        records = [
            _rec("a", T0, spend=0.010),
            _rec("b", T0 + 1, spend=0.002),
        ]
        report = build_weekly_report(records, T0)
        assert report.spend_total_usd == 0.012
        assert report.spend_mean_usd == 0.006
        assert report.spend_p95_usd == 0.01

    def test_latency_none_when_absent(self) -> None:
        report = build_weekly_report([_rec("a", T0)], T0)
        assert report.latency_p50_ms is None


class TestOverrideLedger:
    def test_overrides_counted_when_ledger_present(self) -> None:
        records = [
            _rec("a", T0, override=False),
            _rec("b", T0 + 1, override=True),
        ]
        report = build_weekly_report(records, T0)
        assert report.override_ledger_present is True
        assert report.guardian_overrides == 1

    def test_absent_ledger_disclosed_honestly(self) -> None:
        report = build_weekly_report([_rec("a", T0, override=None)], T0)
        assert report.override_ledger_present is False
        assert report.guardian_overrides == 0
        assert "not present" in render_markdown(report)


class TestDynamoAdapter:
    def test_attributemap_item_parses(self) -> None:
        item = {
            "pk": {"S": "HOUSEHOLD#fam-9"},
            "sk": {"S": "CASE#c-77"},
            "verdict": {"S": "SAFE"},
            "triage_class": {"S": "INFO"},
            "reason_codes": {"SS": ["NONE"]},
            "spend_usd": {"N": "0.0031"},
            "degraded_flags": {"SS": ["NONE"]},
            "created_at": {"N": str(T0)},
        }
        record = _record_from_item(item)
        assert record.household_id == "fam-9"
        assert record.case_id == "c-77"
        assert record.created_at == T0
        assert record.spend_usd == 0.0031
        assert record.degraded_flags == []
        assert record.reason_codes == []

    def test_plain_dict_item_parses(self) -> None:
        record = _record_from_item({"case_id": "x", "created_at": T0, "verdict": "SCAM"})
        assert record.verdict == "SCAM"


class TestRender:
    def test_markdown_contains_core_rows(self) -> None:
        records = [_rec("a", T0, verdict="SCAM"), _rec("b", T0 + 1)]
        text = render_markdown(build_weekly_report(records, T0))
        for needle in ("Cases screened | 2", "| SCAM | 1 |", "Quiet week"):
            assert needle in text
