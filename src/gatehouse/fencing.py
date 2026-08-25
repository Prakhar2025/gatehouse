"""The fencing layer: untrusted content never enters a prompt unwrapped.

Implements docs/08 section 4 as code. Pipeline per case:

    1. normalize      unicode NFKC, zero-width removal, control-char strip
    2. escape         instruction-shaped spans annotated, not silently dropped
    3. wrap           content embedded in explicit untrusted-signal tags
    4. canary         unique token embedded; any appearance outbound = alarm

The canary is the tripwire: if it ever appears in an agent's output, an
injection either leaked through or the model parroted the wrapper. Either way
the case must be flagged CRITICAL upstream (orchestrator contract).
"""

from __future__ import annotations

import re
import secrets
import unicodedata
from dataclasses import dataclass

# Instruction-shaped patterns worth annotating. Matching text stays visible to
# the model but is wrapped in visible markers so a well-prompted agent treats
# it as quoted evidence rather than instructions.
_INSTRUCTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\bignore\s+(all\s+)?(previous|prior|above)\b"),
    re.compile(r"(?i)\bsystem\s*prompt\b"),
    re.compile(r"(?i)\byou\s+are\s+now\b"),
    re.compile(r"(?i)\bnew\s+instructions?\b"),
    re.compile(r"(?i)\bdisregard\b"),
    re.compile(r"(?i)</?untrusted_signal\b"),
)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ZWSP = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")

CANARY_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


@dataclass(frozen=True)
class FencedContent:
    """Result of running one payload through the fence."""

    wrapped: str  # exactly what agents may see
    canary: str  # secret token; orchestrator keeps, never prompts with it
    flagged_spans: int  # count of instruction-shaped annotations applied


def normalize(text: str) -> str:
    """NFKC-fold, drop zero-width and control characters, collapse newlines."""
    folded = unicodedata.normalize("NFKC", text)
    folded = _ZWSP.sub("", folded)
    return _CONTROL.sub("", folded)


def annotate_instructions(text: str) -> tuple[str, int]:
    """Wrap instruction-shaped spans in visible quote markers."""
    flagged = 0
    out = text
    for pattern in _INSTRUCTION_PATTERNS:

        def _wrap(match: re.Match[str]) -> str:
            nonlocal flagged
            flagged += 1
            return f"[QUOTED_EVIDENCE]{match.group(0)}[/QUOTED_EVIDENCE]"

        out = pattern.sub(_wrap, out)
    return out, flagged


def make_canary() -> str:
    """Unpredictable per-case canary token (12 chars, unambiguous alphabet)."""
    return "ghc_" + "".join(secrets.choice(CANARY_ALPHABET) for _ in range(12))


def fence(raw: str, signal_id: str) -> FencedContent:
    """Run the full pipeline over one raw payload."""
    clean = annotate_instructions(normalize(raw))[0]
    # keep the flag count from normalization pass too
    _, flagged = annotate_instructions(clean)
    canary = make_canary()
    wrapped = (
        f'<untrusted_signal id="{signal_id}">\n{clean}\n</untrusted_signal>\nAudit marker: {canary}'
    )
    return FencedContent(wrapped=wrapped, canary=canary, flagged_spans=flagged)


def contains_canary(text: str, canary: str) -> bool:
    """True if the canary leaked into any outbound artifact."""
    return canary in text
