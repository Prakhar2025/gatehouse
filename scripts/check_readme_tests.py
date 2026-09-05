"""Doc-claims drift check: the README must never claim a test count the
repository cannot back (what-broke 2026-09-01). Fails when the number in
README.md drifts from the collected suite size.
"""

import re
import subprocess
import sys
from pathlib import Path

readme = Path("README.md").read_text(encoding="utf-8")
match = re.search(r"(\d+)-test suite", readme)
if not match:
    print("no test-count claim found in README.md; nothing to check")
    sys.exit(0)

claimed = int(match.group(1))
out = subprocess.run(
    [sys.executable, "-m", "pytest", "--collect-only"],
    capture_output=True,
    text=True,
)
m2 = re.search(r"(\d+) tests? collected", out.stdout)
if not m2:
    print("could not read pytest collection output")
    sys.exit(1)
actual = int(m2.group(1))

if claimed != actual:
    print(f"README claims {claimed}-test suite; pytest collects {actual}. Fix the claim.")
    sys.exit(1)
print(f"doc claims ok: {actual} tests collected, README agrees")
