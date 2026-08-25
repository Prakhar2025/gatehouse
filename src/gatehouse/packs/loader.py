"""Pack loading and validation.

Packs are immutable artifacts (doc 09): the loader parses YAML into typed
models, refuses unknown fields or malformed content, and exposes checksums so
every case can pin the exact pack bytes that judged it.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from gatehouse.packs.schemas import CountryPack


class PackError(Exception):
    """Raised when a pack artifact is missing, unreadable, or invalid."""


def compute_checksum(path: Path) -> str:
    """SHA-256 of raw file bytes; pinned in evidence bundles."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_pack(path: Path) -> CountryPack:
    """Parse and validate a pack YAML file.

    Raises:
        PackError: file missing, unparsable YAML, or schema violations.
    """
    if not path.is_file():
        raise PackError(f"pack file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PackError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise PackError(f"pack root must be a mapping, got {type(raw).__name__}")
    try:
        return CountryPack.model_validate(raw)
    except Exception as exc:  # pydantic ValidationError rewrapped uniformly
        raise PackError(f"schema violation in {path}: {exc}") from exc


def validate_pack_dir(packs_root: Path) -> list[tuple[str, str]]:
    """Validate every pack under packs_root; returns [(name, status)].

    Used by `make pack-validate` and CI. A single failure fails the run.
    """
    results: list[tuple[str, str]] = []
    if not packs_root.is_dir():
        raise PackError(f"packs root missing: {packs_root}")
    for path in sorted(packs_root.rglob("*.yaml")):
        name = str(path.relative_to(packs_root))
        try:
            pack = load_pack(path)
            results.append((name, f"OK v{pack.version}"))
        except PackError as exc:
            results.append((name, f"FAIL: {exc}"))
    if not results:
        raise PackError(f"no packs found under {packs_root}")
    return results
