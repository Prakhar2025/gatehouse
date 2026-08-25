"""Deterministic rule classifier: the offline brain.

Contract (docs/03 ADR-1, docs/04 section 3 failure mode):
Scores a signal using ONLY pack lexicons, pack scoring weights, and cheap
structural features (URL presence, payment intent). No model calls, no network,
seed-free and reproducible. This module is:

- the P2 fallback when the triage LLM is down (RULE_ONLY mode),
- the baseline every learned system must beat in evals,
- proof that ADR-4 holds: ALL weights are read from the pack, none hardcoded.

Score composition:

    base  = strongest single lexicon match tier (weak/moderate/strong)
    score = base + payment_intent_bonus? + url_bonus?, capped at 1.0

The engine NEVER produces a final verdict by itself in production; it emits a
score plus matched evidence for upstream policy. Verdict mapping lives in
policy code so thresholds can be tuned without touching detection.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gatehouse.constants import MAX_DISTINCT_COUNTED, RULE_CORROBORATION_STEP
from gatehouse.packs.schemas import CountryPack


@dataclass(frozen=True)
class RuleMatch:
    """One lexicon hit with its tier label and realized weight."""

    phrase: str
    lang: str
    tier: str  # "strong" | "moderate" | "weak"
    weight: float


@dataclass(frozen=True)
class RuleResult:
    """Outcome of one deterministic pass over one signal."""

    score: float
    matches: tuple[RuleMatch, ...] = field(default_factory=tuple)
    has_url: bool = False
    payment_intent: bool = False

    @property
    def rule_class(self) -> str:
        """Coarse class from score bands (doc 04 escalation ladder)."""
        if self.score >= 0.70:
            return "DECISION"
        if self.score >= 0.40:
            return "SCREEN"
        if self.score > 0.0:
            return "INFO"
        return "NOISE"


_PAYMENT_TOKENS = ("upi", "pay now", "payment", "पेमेंट", "भुगतान")


def _matches_in(
    text_lower: str, phrases: list[str], tier: str, weight: float, lang: str
) -> list[RuleMatch]:
    return [
        RuleMatch(phrase=p, lang=lang, tier=tier, weight=weight)
        for p in phrases
        if p.lower() in text_lower
    ]


def classify_text(text: str, pack: CountryPack) -> RuleResult:
    """Score free text against the pack. Deterministic and side-effect free.

    Scoring model (analyst-style evidence stacking):

        base = strongest single lexicon tier hit, plus RULE_CORROBORATION_STEP
               for each ADDITIONAL distinct phrase, up to MAX_DISTINCT_COUNTED
               distinct phrases total. Repeating one phrase adds nothing;
               independent signals stack sub-linearly.
        score = base + payment_intent_bonus? + url_present_bonus?, capped 1.0
    """
    text_lower = text.lower()
    s = pack.scoring
    found: list[RuleMatch] = []
    for lexicon in pack.lexicons:
        found.extend(
            _matches_in(text_lower, lexicon.strong, "strong", s.strong_phrase, lexicon.lang)
        )
        found.extend(
            _matches_in(text_lower, lexicon.moderate, "moderate", s.moderate_phrase, lexicon.lang)
        )
        found.extend(_matches_in(text_lower, lexicon.weak, "weak", s.weak_phrase, lexicon.lang))

    # Distinct phrases only: repeating the same phrase is still one signal.
    distinct = {m.phrase: m for m in found}
    base = 0.0
    if distinct:
        strongest_weight = max(m.weight for m in distinct.values())
        extra_count = min(len(distinct) - 1, MAX_DISTINCT_COUNTED - 1)
        base = min(1.0, strongest_weight + extra_count * RULE_CORROBORATION_STEP)

    payment_intent = any(token in text_lower for token in _PAYMENT_TOKENS)
    has_url = "http://" in text_lower or "https://" in text_lower or "www." in text_lower

    score = base
    if payment_intent:
        score += s.payment_intent_bonus
    if has_url:
        score += s.url_present_bonus
    score = min(score, 1.0)

    return RuleResult(
        score=round(score, 4),
        matches=tuple(found),
        has_url=has_url,
        payment_intent=payment_intent,
    )
