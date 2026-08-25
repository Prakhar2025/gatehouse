#!/usr/bin/env python
"""Validate every country pack artifact under packs/.

Exit codes: 0 all valid, 1 any failure or missing root. Used by Makefile and CI.
"""

from __future__ import annotations

import sys
from pathlib import Path

from gatehouse.packs.loader import validate_pack_dir


def main() -> int:
    root = Path(__file__).resolve().parents[1] / "packs"
    try:
        results = validate_pack_dir(root)
    except Exception as exc:
        print(f"pack validation error: {exc}", file=sys.stderr)
        return 1
    failures = 0
    for name, status in results:
        print(f"{name}: {status}")
        if not status.startswith("OK"):
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
