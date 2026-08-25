"""Typed configuration for all Gatehouse components.

Every knob is environment-driven via pydantic-settings so no secret or
environment-specific value ever reaches source control. Construction fails fast
on invalid values: a misconfigured Gatehouse must refuse to start rather than
degrade silently.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "staging", "prod"]


class Settings(BaseSettings):
    """Process-wide settings, loaded once from the environment."""

    model_config = SettingsConfigDict(
        env_prefix="GATEHOUSE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- identity ---
    environment: Environment = "local"
    region: str = "us-east-1"

    # --- spend governance (charter section 8) ---
    max_model_calls_per_investigation: int = Field(default=12, ge=1, le=64)
    max_usd_per_investigation: float = Field(default=0.02, gt=0)
    breaker_hourly_call_cap: int = Field(default=600, ge=1)

    # --- verdict thresholds (doc 04, pack-overridable) ---
    escalation_floor: float = Field(default=0.40, ge=0, le=1)
    gray_band_low: float = Field(default=0.40, ge=0, le=1)
    gray_band_high: float = Field(default=0.75, ge=0, le=1)
    silent_kill_floor: float = Field(default=0.95, ge=0, le=1)

    # --- dedupe ---
    dedupe_ttl_hours: int = Field(default=72, ge=1)

    # --- graph key derivation (doc 06 section 3; HMAC salt) ---
    graph_salt: str = "gatehouse-dev-salt-change-me"

    # --- telegram channel (doc 05 section 2; secrets via env only) ---
    telegram_webhook_secret: str = ""
    telegram_bot_token: str = ""

    # --- whatsapp channel (doc 05 section 3; disabled until Meta review clears) ---
    whatsapp_enabled: bool = False
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""

    # --- notification service (doc 05 section 6) ---
    quiet_hours_enabled: bool = True
    quiet_hours_utc_offset_minutes: int = Field(default=330, ge=-720, le=840)  # IST default
    guardian_telegram_chat_id: str = ""

    # --- email channel (doc 05 section 4) ---
    email_alias_allowlist: str = ""  # comma-separated bound aliases, e.g. "h7k2,k9m4"

    # --- engage agent (doc 04 section 6; opt-in per household) ---
    engagement_default_opt_in: bool = True

    # --- live deployment wiring (doc 09 section 2) ---
    cases_table_name: str = "gatehouse-cases-staging"
    graph_table_name: str = "gatehouse-graph-staging"
    event_bus_name: str = "gatehouse-events-staging"
    bedrock_model_id: str = "amazon.nova-micro-v1:0"

    @model_validator(mode="after")
    def _bands_ordered(self) -> Settings:
        """Threshold bands must be monotonic; refuse to boot otherwise."""
        if self.gray_band_low > self.gray_band_high:
            raise ValueError("gray_band_low must be <= gray_band_high")
        if self.gray_band_high >= self.silent_kill_floor:
            raise ValueError("silent_kill_floor must exceed gray_band_high")
        if self.environment == "prod" and self.graph_salt.startswith("gatehouse-dev"):
            raise ValueError("prod requires a real GATEHOUSE_GRAPH_SALT")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached accessor; tests override via GATEHOUSE_* env vars."""
    return Settings()
