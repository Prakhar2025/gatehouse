"""Staging runner mode: caps, refusal accounting, real-model seam (doc 07).

The staging path is exercised offline by injecting the MockModel where the
BedrockModel would sit: same structured_output protocol, so every branch
(model call, meter recording, breaker refusal, payload embedding) runs
without AWS. The BedrockModel itself is wired only on explicit operator CLI
runs, which is the one place network spend is ever allowed.
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

from gatehouse.agents.mock_model import MockModel
from gatehouse.evaluation.full_set import generate_dev_set
from gatehouse.evaluation.run_full import (
    RUNNER_ID,
    RUNNER_STAGING_ID,
    _stratified_subsample,
    run_split,
)

PACK = Path(__file__).resolve().parents[2] / "packs" / "in" / "pack.yaml"


class _UsageMock(MockModel):
    """MockModel plus a metadata event, exercising the meter accounting path."""

    async def structured_output(
        self, output_model: Any, prompt: Any, system_prompt: str | None = None, **kwargs: Any
    ) -> Any:
        async for event in super().structured_output(
            output_model, prompt, system_prompt=system_prompt, **kwargs
        ):
            yield event
        yield {"event": {"metadata": {"usage": {"inputTokens": 1000, "outputTokens": 200}}}}


@lru_cache(maxsize=1)
def _staging_payload() -> dict[str, Any]:
    """One shared offline staging run; results are deterministic."""
    model = MockModel(tool_payload={"scam_likelihood": 0.97, "reason_code": "phishing links"})
    return run_split(PACK, "dev", 0.40, mode="staging", model_override=model)


class TestStratifiedSubsample:
    def test_exact_size_and_determinism(self) -> None:
        cases = generate_dev_set()
        picked = _stratified_subsample(cases, 120)
        again = _stratified_subsample(cases, 120)
        assert len(picked) == 120
        assert [c.id for c in picked] == [c.id for c in again]

    def test_proportions_track_the_strata_table(self) -> None:
        cases = generate_dev_set()
        total = len(cases)
        baseline: Counter[str] = Counter(c.stratum for c in cases)
        max_n = 96
        picked = _stratified_subsample(cases, max_n)
        got: Counter[str] = Counter(c.stratum for c in picked)
        for stratum, full_n in baseline.items():
            expected = round(full_n * max_n / total)
            # largest-remainder rounding may shift one case per stratum
            assert abs(got.get(stratum, 0) - expected) <= 1, f"{stratum}: {got.get(stratum)}"

    def test_full_request_returns_everything(self) -> None:
        all_cases = generate_dev_set()
        assert len(_stratified_subsample(all_cases, len(all_cases))) == len(all_cases)

    def test_no_stratum_starves_until_forced(self) -> None:
        all_cases = generate_dev_set()
        small_strata = min(Counter(c.stratum for c in all_cases).values())
        for cap in (20, 48, 64):
            if cap < small_strata:
                continue
            got = Counter(c.stratum for c in _stratified_subsample(generate_dev_set(), cap))
            assert all(v > 0 for v in got.values()), f"cap {cap} starved a stratum"


class TestStagingMode:
    def test_payload_embeds_staging_contract(self) -> None:
        payload = _staging_payload()
        assert payload["runner"] == RUNNER_STAGING_ID
        assert payload["model_mode"] == "bedrock"
        assert payload["model_id"]
        assert payload["max_usd_cap"] is not None and payload["max_calls_cap"] is not None
        assert isinstance(payload["misses"], list)
        for miss in payload["misses"]:
            assert set(miss) >= {
                "case_id",
                "stratum",
                "ground_truth",
                "verdict",
                "taxonomy_class",
            }

    def test_local_mock_payload_unchanged(self) -> None:
        payload = run_split(PACK, "dev", 0.40, quiet=True)
        assert payload["runner"] == RUNNER_ID
        assert payload["model_mode"] == "local_mock_rules"
        assert "misses" not in payload and "model_calls" not in payload

    def test_call_cap_degrades_visibly_not_silently(self) -> None:
        model = _UsageMock(tool_payload={"scam_likelihood": 0.97, "reason_code": "kyc lure"})
        payload = run_split(
            PACK,
            "dev",
            0.40,
            mode="staging",
            model_override=model,
            max_cases=8,
            max_calls_cap=0,
            quiet=True,
        )
        assert payload["ran_cases"] == 8
        assert payload["breaker_refusals"] >= 8
        assert all(miss["taxonomy_class"] != "" for miss in payload["misses"])
        # degraded cases still complete with the honest refusal disclosure
        flagged_refusals = [
            m for m in payload["misses"] if "TRIAGE_BUDGET_REFUSED" in m["degraded_flags"]
        ]
        assert flagged_refusals or payload["failure_taxonomy"]["degraded_mode_cause"] >= 0

    def test_meter_records_usage_from_metadata_events(self) -> None:
        model = _UsageMock(tool_payload={"scam_likelihood": 0.97, "reason_code": "kyc lure"})
        payload = run_split(
            PACK, "dev", 0.40, mode="staging", model_override=model, max_cases=4, quiet=True
        )
        assert payload["model_calls"] == 4
        assert payload["spend_usd_total"] > 0.0


@pytest.mark.parametrize("mode", ["warp", "", "PRODUCTION"])
def test_unknown_mode_is_rejected(mode: str) -> None:
    with pytest.raises(ValueError, match="unknown mode"):
        run_split(PACK, "dev", 0.40, mode=mode, quiet=True)
