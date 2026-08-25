#!/usr/bin/env python3
"""Register the Telegram webhook against the deployed API and verify it.

Usage: python scripts/set_webhook.py <api_base_url>

Reads GATEHOUSE_TELEGRAM_BOT_TOKEN and GATEHOUSE_TELEGRAM_WEBHOOK_SECRET from
the environment. Never prints either value.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request


def _call(token: str, method: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        out: dict[str, object] = json.loads(resp.read().decode())
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: set_webhook.py <api_base_url>", file=sys.stderr)
        return 2
    token = os.environ.get("GATEHOUSE_TELEGRAM_BOT_TOKEN", "")
    secret = os.environ.get("GATEHOUSE_TELEGRAM_WEBHOOK_SECRET", "")
    if not token or not secret:
        print("missing GATEHOUSE_TELEGRAM_BOT_TOKEN or GATEHOUSE_TELEGRAM_WEBHOOK_SECRET", file=sys.stderr)
        return 2
    base = argv[1].rstrip("/")
    webhook_url = f"{base}/telegram"
    result = _call(token, "setWebhook", {"url": webhook_url, "secret_token": secret})
    ok = bool(result.get("ok"))
    print(f"setWebhook: {'ok' if ok else 'FAILED'}")
    info = _call(token, "getWebhookInfo")
    assert isinstance(info.get("result"), dict)
    r = info["result"]
    print(f"webhook url registered: {r.get('url') == webhook_url}")
    print(f"pending updates: {r.get('pending_update_count')}")
    if r.get("last_error_message"):
        print(f"last error: {r.get('last_error_message')}", file=sys.stderr)
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
