"""Tests for the mini runner CLI."""

from __future__ import annotations

import json
from pathlib import Path

from gatehouse.evaluation.generator import MINI_SET_SIZE
from gatehouse.evaluation.run_mini import main, run

REPO = Path(__file__).resolve().parents[1]
PACK = REPO / "packs" / "in" / "pack.yaml"


def test_run_payload_complete() -> None:
    payload = run(PACK)
    for key in (
        "cases",
        "tp",
        "fp",
        "tn",
        "fn",
        "precision",
        "precision_ci",
        "recall",
        "recall_ci",
        "false_gate_rate",
        "per_stratum",
    ):
        assert key in payload
    assert payload["pack_version"] == "0.1.0"
    assert payload["runner"] == "mini-rule-v0"


def test_deterministic_json(tmp_path: Path) -> None:
    out_a = tmp_path / "a.json"
    out_b = tmp_path / "b.json"
    main(["--pack", str(PACK), "--json", str(out_a)])
    main(["--pack", str(PACK), "--json", str(out_b)])
    assert out_a.read_bytes() == out_b.read_bytes()
    payload = json.loads(out_a.read_text())
    assert payload["cases"] == MINI_SET_SIZE


def test_per_stratum_table_covers_all_nine() -> None:
    payload = run(PACK)
    names = {s["stratum"] for s in payload["per_stratum"]}
    expected = {
        "kyc_scam",
        "digital_arrest",
        "investment",
        "lottery",
        "legit_bank_offer",
        "delivery_update",
        "family_chatter",
        "otp_forward",
        "govt_legit_trap",
    }
    assert names == expected
