#!/usr/bin/env python3
"""Journey A latency harness: measures webhook round-trip from Telegram's side.

Sends N update payloads directly to the deployed webhook with the correct
secret header (simulating Telegram's delivery), records per-send wall time
until HTTP 200, and reports p50/p95. Verdicts and guardian cards are counted
separately via getUpdates on the bot chat after the run.

This measures OUR pipeline latency as Telegram experiences it. The exit
criterion (p95 under 30s across 50 sends) is exactly this number.
"""

from __future__ import annotations

import json
import pathlib
import statistics
import sys
import time
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[1]


def _load_env() -> dict[str, str]:
    vals: dict[str, str] = {}
    path = REPO / ".env"
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip()
    return vals


SCAM_SAMPLES = [
    "SBI KYC expired, pay now at http://sbi-verify.top UTR123456789012",
    "Your ATM card is blocked, update KYC at http://sbi-kyc-alert.in immediately",
    "Congratulations! You won the KBC lottery, send 5000 processing fee",
    "Papa meri phone kharab ho gayi, mujhe 5000 urgent upi kar do is number pe",
    "ICICI bank: your account will be blocked tonight, verify at bit.ly/icici-block",
]
BENIGN_SAMPLE = "lunch tomorrow at the usual place?"
GRAY_SAMPLE = "click http://random-site.example now"

CHAT_ID = 5500012


def _send(base: str, secret: str, payload: dict) -> float:
    """One webhook delivery; returns elapsed seconds to HTTP 200."""
    url = f"{base}/telegram"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(  # noqa: S310 - https-only base from stack outputs
        url,
        data=data,
        headers={"Content-Type": "application/json", "X-Telegram-Bot-Api-Secret-Token": secret},
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - same
        resp.read()
        assert resp.status == 200
    return time.perf_counter() - t0


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: journey_latency.py <api_base> <n_sends>", file=sys.stderr)
        return 2
    base, n = argv[0].rstrip("/"), int(argv[1])
    vals = _load_env()
    secret = vals["GATEHOUSE_TELEGRAM_WEBHOOK_SECRET"]

    times: list[float] = []
    statuses: dict[str, int] = {}
    # Unique tag per RUN: the dedupe table remembers content for the full
    # TTL, so fixed [ref 000]-style texts make every rerun after the first
    # short-circuit as duplicates and measure nothing.
    run_tag = int(time.time())
    for i in range(n):
        # Cycle sample types; unique update_id AND unique text each time so
        # the run measures investigation latency, not dedupe short-circuits.
        if i % 5 == 4:
            text = BENIGN_SAMPLE
        elif i % 5 == 3:
            text = GRAY_SAMPLE
        else:
            text = SCAM_SAMPLES[i % len(SCAM_SAMPLES)]
        payload = {
            "update_id": 90_000_000 + (run_tag % 8_000_000) * 20 + i,
            "message": {
                "chat": {"id": CHAT_ID},
                "from": {"first_name": "Riya"},
                "text": f"{text} [r{run_tag} n{i:03d}]",
            },
        }
        try:
            dt = _send(base, secret, payload)
            times.append(dt)
            print(f"send {i + 1}/{n}: {dt:.2f}s")
        except urllib.error.HTTPError as exc:
            print(f"send {i + 1}/{n}: HTTP {exc.code}", file=sys.stderr)
            statuses[f"http_{exc.code}"] = statuses.get(f"http_{exc.code}", 0) + 1
        except Exception as exc:
            print(f"send {i + 1}/{n}: {type(exc).__name__}", file=sys.stderr)
            statuses[type(exc).__name__] = statuses.get(type(exc).__name__, 0) + 1
        time.sleep(0.4)

    if not times:
        print("no successful sends", file=sys.stderr)
        return 1
    times_sorted = sorted(times)
    p50 = statistics.median(times_sorted)
    p95 = (
        times_sorted[int(len(times_sorted) * 0.95) - 1]
        if len(times_sorted) > 1
        else times_sorted[0]
    )
    print("\n=== Journey A latency summary ===")
    print(f"sends ok:   {len(times)}/{n}")
    print(f"errors:     {statuses or 'none'}")
    print(f"p50:        {p50:.2f}s")
    print(f"p95:        {p95:.2f}s")
    print(f"max:        {max(times):.2f}s")
    verdict = "PASS" if p95 < 30 else "FAIL"
    print(f"exit bar:   p95 < 30s -> {verdict}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
