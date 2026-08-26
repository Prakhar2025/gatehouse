"""Read recent case_trace lines from the staging intake log group.

Operational tool for the P4 observability contract (doc 03): prove any case
reconstructs end to end from its single trace line. Prints one block per
case: id, channel, status, verdict, spend, degradation flags, and the timed
stage list. Read-only; prints nothing but parsed fields, never raw payloads,
so member data cannot leak into terminals or chat logs.

Usage:
    python scripts/read_traces.py [minutes_back]
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any

import boto3


def main() -> int:
    minutes_back = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    logs = boto3.client("logs", region_name="ap-south-1")
    group = "/aws/lambda/gatehouse-intake-staging"
    resp = logs.filter_log_events(
        logGroupName=group,
        startTime=int((time.time() - minutes_back * 60) * 1000),
        filterPattern='"case_trace"',
    )
    events = resp.get("events", [])
    print(f"case_trace lines in last {minutes_back}m: {len(events)}")
    for event in events:
        message = event["message"]
        start = message.find("{")
        if start < 0:
            continue
        rec: dict[str, Any] = json.loads(message[start:])
        ctx = rec.get("ctx", {})
        facts = ctx.get("facts", {})
        print(
            f"case {ctx.get('case_id')} | {ctx.get('channel')} | "
            f"status={ctx.get('status')} | total_ms={ctx.get('total_ms')}"
        )
        print(
            f"  verdict={facts.get('verdict')} spend_usd={facts.get('spend_usd')} "
            f"degraded={facts.get('degraded')}"
        )
        for span in ctx.get("stages", []):
            suffix = f" err={span['err']}" if span.get("err") else ""
            print(f"  {span['stage']:9} {span['status']:7} {span['ms']}ms{suffix}")
        print("---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
