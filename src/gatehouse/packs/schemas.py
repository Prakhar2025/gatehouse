"""Country pack data models (doc 03 ADR-4, doc 06 section 4).

A pack is DATA, not code: rails, issuer registries, scam lexicons, and scoring
constants for one region. Schemas here are the contract between pack authors
and every consumer (rules engine, agents, validators). Unknown fields are
rejected so typos cannot silently weaken a pack.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --- shared primitives ---

SafeText = Annotated[str, Field(min_length=1, max_length=200)]
SemVer = Annotated[str, Field(pattern=r"^\d+\.\d+\.\d+$")]

# Canonical stratum ordering for byte-stable reports (doc 07).
STRATA_ORDER: tuple[str, ...] = (
    "kyc_scam",
    "digital_arrest",
    "investment",
    "lottery",
    "legit_bank_offer",
    "delivery_update",
    "family_chatter",
    "otp_forward",
    "govt_legit_trap",
)


class ScoringConfig(BaseModel):
    """Deterministic rule-engine weights; mirrored by constants.py defaults."""

    model_config = ConfigDict(extra="forbid")

    strong_phrase: float = Field(ge=0.0, le=1.0)
    moderate_phrase: float = Field(ge=0.0, le=1.0)
    weak_phrase: float = Field(ge=0.0, le=1.0)
    payment_intent_bonus: float = Field(ge=0.0, le=1.0)
    url_present_bonus: float = Field(ge=0.0, le=1.0)


class Issuer(BaseModel):
    """One trusted institution with its verified contact surface."""

    model_config = ConfigDict(extra="forbid")

    id: SafeText
    name: SafeText
    official_domains: list[str] = Field(min_length=1)
    sms_sender_ids: list[str] = Field(default_factory=list)

    @field_validator("official_domains", "sms_sender_ids")
    @classmethod
    def _lowercase(cls, value: list[str]) -> list[str]:
        return [item.lower() for item in value]


class Rail(BaseModel):
    """Payment rail grammar: what a legitimate request looks like."""

    model_config = ConfigDict(extra="forbid")

    id: SafeText  # e.g. "upi"
    display_name: SafeText
    vpa_pattern: str | None = None  # compiled at load time
    collect_request_fields: list[str] = Field(default_factory=list)

    @field_validator("vpa_pattern")
    @classmethod
    def _compilable(cls, value: str | None) -> str | None:
        if value is not None:
            re.compile(value)  # raises on bad pattern: fail fast
        return value


class Lexicon(BaseModel):
    """Scam phrase lists per language with match weights."""

    model_config = ConfigDict(extra="forbid")

    lang: Annotated[str, Field(pattern=r"^[a-z]{2}$")]
    strong: list[SafeText] = Field(default_factory=list)
    moderate: list[SafeText] = Field(default_factory=list)
    weak: list[SafeText] = Field(default_factory=list)


class CountryPack(BaseModel):
    """Root manifest for one regional pack version."""

    model_config = ConfigDict(extra="forbid")

    region: Annotated[str, Field(pattern=r"^[a-z]{2}$")]
    version: SemVer
    languages: list[Annotated[str, Field(pattern=r"^[a-z]{2}$")]] = Field(min_length=1)
    scoring: ScoringConfig
    issuers: list[Issuer] = Field(default_factory=list)
    rails: list[Rail] = Field(default_factory=list)
    lexicons: list[Lexicon] = Field(min_length=1)

    def issuer_domains(self) -> frozenset[str]:
        """All trusted domains across issuers, lowercased."""
        return frozenset(
            domain.lower() for issuer in self.issuers for domain in issuer.official_domains
        )

    def issuer_sms_senders(self) -> frozenset[str]:
        """All trusted SMS sender IDs across issuers, lowercased."""
        return frozenset(
            sender.lower() for issuer in self.issuers for sender in issuer.sms_sender_ids
        )


@lru_cache(maxsize=8)
def compile_vpa_pattern(pack_region_version: tuple[str, str], pattern: str) -> re.Pattern[str]:
    """Cache compiled rail patterns keyed by (region, version)."""
    return re.compile(pattern)
