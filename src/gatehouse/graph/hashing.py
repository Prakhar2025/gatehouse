"""Privacy-preserving identifier hashing for the threat graph boundary.

Contract (docs/06 section 3, docs/08 checklist item 8): only keyed hashes
(HMAC-SHA256, truncated) ever cross into graph storage. Raw identifiers exist
solely inside the case sandbox. The key comes from settings (env/SSM); prod
refuses to boot with the dev salt (config validator).
"""

from __future__ import annotations

import hashlib
import hmac

from gatehouse.config import Settings

_HASH_LEN = 32  # hex chars (16 bytes): collision-safe at our scale, privacy-cheap


def _hmac_hex(key: bytes, message: str) -> str:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).hexdigest()[:_HASH_LEN]


def hash_identifier(kind: str, raw_value: str, salt: str) -> str:
    """Keyed hash of one identifier. Kind is mixed in to separate namespaces."""
    key = salt.encode("utf-8")
    return _hmac_hex(key, f"{kind.upper()}:{raw_value.strip().lower()}")


def hash_for_settings(kind: str, raw_value: str, settings: Settings) -> str:
    """Convenience wrapper binding the configured salt."""
    return hash_identifier(kind, raw_value, settings.graph_salt)


def extract_identifiers(text: str) -> list[tuple[str, str]]:
    """Pull raw identifiers from text. Returns (kind, value) pairs.

    Deliberately conservative: high-precision patterns only. Misses are fine
    (the graph grows on what agents explicitly extract later); false positives
    pollute the graph, so we do not guess.
    """
    import re

    out: list[tuple[str, str]] = []

    # VPA: name@bank (bank side alphabetic, 2+ chars)
    for match in re.finditer(r"\b([a-zA-Z0-9._-]{2,})@([a-zA-Z]{2,})\b", text):
        out.append(("VPA", f"{match.group(1)}@{match.group(2)}"))

    # Phones: E.164-ish, 10-13 digits with optional + and separators
    for match in re.finditer(r"(?<![\w])(?:\+?91[- ]?)?[6-9]\d{9}(?![\w])", text):
        out.append(("PHONE", match.group(0)))

    # UTR refs: UPI transaction ids
    for match in re.finditer(r"\bUTR[/\s]?([A-Z0-9]{8,22})\b", text, re.IGNORECASE):
        out.append(("UTR_REF", f"UTR{match.group(1)}"))

    return out
