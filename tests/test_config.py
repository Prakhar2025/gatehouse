"""Tests for typed config loading and validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from gatehouse.config import Settings, get_settings


def test_defaults_load() -> None:
    settings = Settings()
    assert settings.environment == "local"
    assert settings.region == "us-east-1"
    assert settings.max_usd_per_investigation > 0


def test_threshold_bands_must_be_ordered() -> None:
    with pytest.raises(ValidationError):
        Settings(gray_band_low=0.9, gray_band_high=0.2)
    with pytest.raises(ValidationError):
        Settings(gray_band_high=0.99, silent_kill_floor=0.95)


def test_environment_literal_enforced() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production")  # not in Literal


def test_spend_governance_bounds() -> None:
    with pytest.raises(ValidationError):
        Settings(max_model_calls_per_investigation=0)
    with pytest.raises(ValidationError):
        Settings(max_usd_per_investigation=-1)


def test_cached_accessor_returns_same_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GATEHOUSE_REGION", "ap-south-1")
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    assert first is second
    assert first.region == "ap-south-1"
    get_settings.cache_clear()
