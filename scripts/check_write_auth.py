#!/usr/bin/env python3
"""Fail the build if a console API write route skips the session check.

The console API serves public reads so the console can be shown without a
password. That split is only safe while every mutating route still proves a
session first. A write route shipped without that check once already: it let
anyone on the internet append override rows stamped as the guardian, into the
very ledger the accuracy numbers are computed from. This check exists so the
same hole cannot reopen quietly.
"""

from __future__ import annotations

import pathlib
import re
import sys

HANDLER = pathlib.Path(__file__).resolve().parents[1] / "lambda" / "console-api.mjs"
# /auth is the one mutating route that cannot require a session: it issues one.
EXEMPT = {"/auth"}
ROUTE_RE = re.compile(r'if \(route === "(?P<route>[^"]+)" && method === "(?P<method>[A-Z]+)"\)')
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def main() -> int:
    source = HANDLER.read_text(encoding="utf-8")
    matches = list(ROUTE_RE.finditer(source))
    if not matches:
        print("no method-guarded routes found: has the handler been restructured?", file=sys.stderr)
        return 1

    failures: list[str] = []
    checked = 0
    for idx, match in enumerate(matches):
        if match.group("method") not in WRITE_METHODS:
            continue
        route = match.group("route")
        if route in EXEMPT:
            continue
        checked += 1
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(source)
        body = source[match.end() : end]
        if "validSession(" not in body:
            failures.append(f"{match.group('method')} {route} writes without checking validSession")

    if failures:
        for line in failures:
            print(f"write-auth: {line}", file=sys.stderr)
        return 1
    if checked == 0:
        print(
            "write-auth: no non-exempt write routes found, check is not proving anything",
            file=sys.stderr,
        )
        return 1
    print(f"write auth ok: {checked} write route(s) require a session")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
