"""Project-wide constants: single source of truth for magic values.

Import from here instead of inlining literals. Anything appearing in more than
one module graduates into this file with a comment explaining its contract.
"""

from __future__ import annotations

# --- redaction ---
REDACTION_TOKEN = "[REDACTED]"  # noqa: S105 - marker string, not a credential
PLACEHOLDER_PREFIX = "GH_"  # typed placeholders look like GH_PHONE_1

# --- verdicts and classes (doc 04 shared schemas) ---
VERDICT_SAFE = "SAFE"
VERDICT_SUSPICIOUS = "SUSPICIOUS"
VERDICT_SCAM = "SCAM"
VERDICT_NEEDS_HUMAN = "NEEDS_HUMAN"

CLASS_NOISE = "NOISE"
CLASS_INFO = "INFO"
CLASS_SCREEN = "SCREEN"
CLASS_DECISION = "DECISION"
CLASS_EMERGENCY = "EMERGENCY"

# --- rule engine scoring (deterministic fallback + eval baseline) ---
RULE_MATCH_WEIGHT_STRONG = 0.45
RULE_MATCH_WEIGHT_MODERATE = 0.30
RULE_MATCH_WEIGHT_WEAK = 0.15
PAYMENT_INTENT_BONUS = 0.20
URL_PRESENT_BONUS = 0.15
# Corroboration: every ADDITIONAL distinct phrase beyond the strongest adds this
# much, sub-linearly. Independent signals stack; repetition of one phrase does not.
RULE_CORROBORATION_STEP = 0.25
MAX_DISTINCT_COUNTED = 3

SCORE_SILENT_KILL = 0.95
SCORE_ESCALATE = 0.70
SCORE_SCREEN = 0.40
