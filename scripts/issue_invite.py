#!/usr/bin/env python3
"""Issue a household invite code (the guardian path until the console lands).

Usage: python scripts/issue_invite.py <household_id> [--write-dynamo]

Without --write-dynamo the code is minted locally for dry-run checks only.
With --write-dynamo it is persisted to the staging bindings table so a
member's /start CODE actually consumes it. When GATEHOUSE_TELEGRAM_BOT_TOKEN
and GATEHOUSE_GUARDIAN_TELEGRAM_CHAT_ID are present in .env / .env.deploy,
the code is also sent to the guardian chat. Never prints the token.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[1]


def _load_env() -> dict[str, str]:
    """Read the repo env file so callers need no shell exports."""
    for name in (".env.deploy", ".env"):
        path = REPO / name
        if not path.exists():
            continue
        vals: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip()
        return vals
    return {}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Issue a Gatehouse household invite code")
    parser.add_argument("household_id", help="household the code binds to, e.g. shukla-home")
    parser.add_argument(
        "--write-dynamo",
        action="store_true",
        help="persist the invite to the staging bindings table so /start can consume it",
    )
    args = parser.parse_args(argv)

    import boto3

    from gatehouse.channels.binding import DynamoBindingStore, InMemoryBindingStore

    env_vals = _load_env()
    region = "ap-south-1"
    table = env_vals.get("GATEHOUSE_CASES_TABLE", "gatehouse-cases-staging")

    if args.write_dynamo:
        client = boto3.client("dynamodb", region_name=region)
        store = DynamoBindingStore(client, table)
        invite = store.issue_invite(args.household_id)
        where = f"DynamoDB table {table}"
    else:
        invite = InMemoryBindingStore().issue_invite(args.household_id)
        where = "LOCAL ONLY (not consumable by the deployed stack)"
    print(f"invite code: {invite.code}")
    print(f"household:   {args.household_id}")
    print(f"stored in:   {where}")
    print(f"member binds with: /start {invite.code}")

    token = env_vals.get("GATEHOUSE_TELEGRAM_BOT_TOKEN", "")
    chat_id = env_vals.get("GATEHOUSE_GUARDIAN_TELEGRAM_CHAT_ID", "")
    if token and chat_id:
        msg = (
            f"Gatehouse invite code for {args.household_id}: {invite.code}\n"
            f"The member sends: /start {invite.code}"
        )
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        req = urllib.request.Request(
            url,
            data=json.dumps({"chat_id": chat_id, "text": msg}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
                out = json.loads(resp.read().decode())
            print(f"sent to guardian chat: {out.get('ok')}")
        except Exception as exc:
            print(f"guardian send failed ({type(exc).__name__}); share the code manually")
    else:
        print("guardian send skipped: token or chat id missing from env file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
