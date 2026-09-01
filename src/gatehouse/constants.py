"""Project-wide constants: single source of truth for magic values.

Import from here instead of inlining literals. Anything appearing in more than
one module graduates into this file with a comment explaining its contract.
"""

from __future__ import annotations

from typing import Literal

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

# The band vocabulary as one literal type. Strings above are its values;
# schemas, the rule classifier, and triage all share this definition.
SignalClass = Literal["NOISE", "INFO", "SCREEN", "DECISION", "EMERGENCY"]

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

# --- graduated silence law (doc 19 section 3) ---
# Silence is the product; alerting is the failure mode we are replacing. The
# band is computed on every case and is the contract the passive arrival
# filters (v1.5+) consume. In v1 it governs whether the GUARDIAN is paged:
# the member who forwarded a signal always gets their answer.
SilenceBand = Literal["SILENT_KILL", "AGENT_SCREEN", "BADGED_RING", "PASS"]

BAND_SILENT_KILL: SilenceBand = "SILENT_KILL"  # no human paged; weekly report entry
BAND_AGENT_SCREEN: SilenceBand = "AGENT_SCREEN"  # a human sees the result, never the panic
BAND_BADGED_RING: SilenceBand = "BADGED_RING"  # surfaced with a risk badge; the human decides
BAND_PASS: SilenceBand = "PASS"  # noqa: S105 - band name, not a credential
