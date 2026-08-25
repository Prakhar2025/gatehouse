"""Tests for the deterministic rule classifier."""

from __future__ import annotations

from pathlib import Path

import pytest

from gatehouse.packs.loader import load_pack
from gatehouse.packs.schemas import CountryPack
from gatehouse.rules.classifier import classify_text

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def pack() -> CountryPack:
    return load_pack(REPO / "packs" / "in" / "pack.yaml")


class TestClassify:
    def test_strong_kyc_scam_with_url_reaches_screen(self, pack: CountryPack) -> None:
        """Strong phrase + link = SCREEN band (0.40-0.69). DECISION needs payment intent too."""
        result = classify_text(
            "Your KYC has expired, verify at https://sbi-kyc.top now or account blocked",
            pack,
        )
        assert result.score >= 0.40
        assert result.has_url is True
        assert any("kyc has expired" in m.phrase for m in result.matches)

    def test_full_kyc_scam_reaches_decision(self, pack: CountryPack) -> None:
        """Strong phrase + URL + payment intent = full escalation band."""
        result = classify_text(
            "Your KYC has expired, pay now at https://sbi-kyc.top or account blocked",
            pack,
        )
        assert result.score >= 0.70
        assert result.payment_intent is True

    def test_digital_arrest_detected(self, pack: CountryPack) -> None:
        result = classify_text("You are under digital arrest, pay penalty via UPI now", pack)
        assert result.payment_intent is True
        assert result.score >= 0.60  # strong hit + payment intent bonus

    def test_hindi_scam_detected(self, pack: CountryPack) -> None:
        result = classify_text("आपका केवाईसी समाप्त हो गया है, तुरंत सत्यापित करें", pack)
        assert result.matches
        assert result.score >= 0.40  # strong phrase present

    def test_benign_bank_offer_stays_low(self, pack: CountryPack) -> None:
        result = classify_text(
            "SBI: Get 2x reward points on all online spends. Login to onlinesbi.sbi", pack
        )
        assert result.score < 0.40

    def test_family_chatter_is_noise(self, pack: CountryPack) -> None:
        result = classify_text("Mummy calling after lunch, call back when free", pack)
        assert result.rule_class == "NOISE"

    def test_weights_come_from_pack_not_code(self, pack: CountryPack) -> None:
        """Mutating pack weights must move scores: weights are data (ADR-4)."""
        from copy import deepcopy

        mutated = deepcopy(pack)
        mutated.scoring.strong_phrase = 0.9
        base = classify_text("kyc expired today", pack).score
        heavier = classify_text("kyc expired today", mutated).score
        assert heavier > base

    def test_cap_at_one(self, pack: CountryPack) -> None:
        wall = " ".join(["kyc expired"] * 20)
        result = classify_text(wall + " upi payment http://x.yz", pack)
        assert result.score <= 1.0

    def test_deterministic(self, pack: CountryPack) -> None:
        text = "urgent kyc expired click http://a.b"
        first = classify_text(text, pack)
        second = classify_text(text, pack)
        assert first == second
