"""Tests for the graduated silence law (doc 19 section 3).

Silence is the product, so the ladder that decides whether a human is paged
gets boundary tests on every rung. Trust dies faster from one silenced
hospital than from a hundred missed scams, which makes the conservative rules
(NEEDS_HUMAN is never silent, SUSPICIOUS never reaches SILENT_KILL) the most
important assertions in this file.
"""

from __future__ import annotations

import pytest

from gatehouse.agents.guardian import compute_silence_band
from gatehouse.agents.schemas import GuardianPackage, Verdict
from gatehouse.config import Settings


@pytest.fixture
def settings() -> Settings:
    """Default bands: screen 0.40, gray high 0.75, silent kill 0.95."""
    return Settings()


class TestBandLadder:
    def test_settled_scam_at_the_floor_is_silent(self, settings: Settings) -> None:
        assert compute_silence_band("SCAM", 0.95, settings) == "SILENT_KILL"

    def test_scam_just_below_the_floor_still_reaches_a_human(self, settings: Settings) -> None:
        """The floor is inclusive on one side only; 0.9499 must not vanish."""
        assert compute_silence_band("SCAM", 0.9499, settings) == "AGENT_SCREEN"

    def test_scam_in_the_gray_band_is_screened(self, settings: Settings) -> None:
        assert compute_silence_band("SCAM", 0.80, settings) == "AGENT_SCREEN"

    def test_scam_above_screen_floor_is_badged(self, settings: Settings) -> None:
        assert compute_silence_band("SCAM", 0.50, settings) == "BADGED_RING"

    def test_weak_scam_below_the_screen_floor_passes(self, settings: Settings) -> None:
        assert compute_silence_band("SCAM", 0.10, settings) == "PASS"


class TestConservativeRules:
    def test_needs_human_is_never_silenced_at_any_confidence(self, settings: Settings) -> None:
        """NEEDS_HUMAN is the pipeline asking for a person. No number overrides that."""
        for confidence in (0.0, 0.5, 0.99, 1.0):
            assert compute_silence_band("NEEDS_HUMAN", confidence, settings) == "BADGED_RING"

    def test_suspicious_never_reaches_silent_kill(self, settings: Settings) -> None:
        """Unsettled evidence is not handled in silence however high it scores."""
        assert compute_silence_band("SUSPICIOUS", 0.99, settings) == "AGENT_SCREEN"
        assert compute_silence_band("SUSPICIOUS", 1.0, settings) == "AGENT_SCREEN"

    def test_safe_is_pass_not_a_suppressed_alarm(self, settings: Settings) -> None:
        """SAFE means nothing was found; confidence there is confidence in safety."""
        for confidence in (0.0, 0.6, 1.0):
            assert compute_silence_band("SAFE", confidence, settings) == "PASS"


class TestConfigurability:
    def test_lowering_the_floor_moves_the_operating_point(self) -> None:
        """Doc 19 acceptance criterion 2: bands ship as configuration."""
        strict = Settings(silent_kill_floor=0.99)
        assert compute_silence_band("SCAM", 0.96, strict) == "AGENT_SCREEN"
        loose = Settings(silent_kill_floor=0.90)
        assert compute_silence_band("SCAM", 0.96, loose) == "SILENT_KILL"

    def test_raising_the_screen_floor_widens_pass(self) -> None:
        wide = Settings(gray_band_low=0.60)
        assert compute_silence_band("SCAM", 0.50, wide) == "PASS"


class TestPackageDefault:
    def test_package_defaults_to_a_human_visible_band(self) -> None:
        """A package that skipped band computation must not be swallowed."""
        pkg = GuardianPackage(verdict="SCAM", confidence=0.99, recommended_action="warn_member")
        assert pkg.silence_band == "BADGED_RING"

    @pytest.mark.parametrize("verdict", ["SAFE", "SUSPICIOUS", "SCAM", "NEEDS_HUMAN"])
    def test_every_verdict_yields_a_valid_band(self, verdict: Verdict, settings: Settings) -> None:
        band = compute_silence_band(verdict, 0.85, settings)
        assert band in {"SILENT_KILL", "AGENT_SCREEN", "BADGED_RING", "PASS"}
