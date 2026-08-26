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
# Legacy P1 strata kept stable; P6 full-set strata appended in doc 07 table order.
STRATA_ORDER: tuple[str, ...] = (
    "kyc_scam",
    "digital_arrest",
    "investment",
    "lottery",
    "upi_collect_fraud",
    "courier_scam",
    "job_task_scam",
    "relative_impersonation",
    "legit_bank_offer",
    "delivery_update",
    "govt_notice_legit",
    "family_chatter",
    "newsletter_promo",
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
    aliases: list[SafeText] = Field(default_factory=list)
    official_domains: list[str] = Field(min_length=1)
    sms_sender_ids: list[str] = Field(default_factory=list)

    @field_validator("official_domains", "sms_sender_ids")
    @classmethod
    def _lowercase(cls, value: list[str]) -> list[str]:
        return [item.lower() for item in value]


class TrustedService(BaseModel):
    """A non-issuer brand whose official link surface is curated.

    E-commerce, logistics, and government portals. Structurally identical to
    Issuer minus SMS sender ids: the same claim-adjudication code path runs
    over both registries in verify.
    """

    model_config = ConfigDict(extra="forbid")

    id: SafeText
    name: SafeText
    aliases: list[SafeText] = Field(default_factory=list)
    official_domains: list[str] = Field(min_length=1)

    @field_validator("official_domains")
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
    # Curated NON-issuer brands that are safe to trust for link-bearing
    # legitimate traffic: e-commerce, logistics, government portals. Kept
    # separate from issuers on purpose: trusting a retailer says nothing
    # about a bank's link surface, and vice versa.
    trusted_services: list[TrustedService] = Field(default_factory=list)

    def trusted_domain_set(self) -> frozenset[str]:
        """All curated trusted-service domains, lowercased."""
        return frozenset(
            domain.lower()
            for service in self.trusted_services
            for domain in service.official_domains
        )

    def claim_registries(self) -> list[Issuer | TrustedService]:
        """Issuers then trusted services, for uniform claim adjudication."""
        return [*self.issuers, *self.trusted_services]

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
