"""Fetch recent case items from the live staging table for soak reporting.

Offline-first contract: the soak MATH lives in gatehouse.evaluation.soak and
is tested without AWS. This script only pulls rows: Scan with pagination over
the cases table (a weekly batch job, not a hot path), projecting exactly the
fields the report consumes, filtering by age client-side, emitting the record
list as JSON. Credentials come from the default chain; region/table from env
(GATEHOUSE_REGION, GATEHOUSE_CASES_TABLE_NAME) so nothing sensitive lands here.

Usage (office wifi or anywhere with credentials):
    python scripts/soak_fetch.py --days 7 > docs/eval-results/soak-records.json
    python -m gatehouse.evaluation.soak --records docs/eval-results/soak-records.json \
        --markdown docs/eval-results/soak-week.md
"""

from __future__ import annotations

import argparse
import json
import sys
import time

PROJECTION = "pk, sk, verdict, triage_class, reason_codes, spend_usd, degraded_flags, created_at"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pull case items for the soak report")
    parser.add_argument("--days", type=int, default=7, help="how far back to look")
    parser.add_argument(
        "--table", type=str, default="", help="overrides GATEHOUSE_CASES_TABLE_NAME"
    )
    parser.add_argument(
        "--region", type=str, default="", help="overrides GATEHOUSE_REGION / default"
    )
    args = parser.parse_args(argv)

    try:
        import boto3  # local/dev dependency; never imported by the app suite
    except ImportError:
        print("boto3 not installed; install dev tooling to fetch live records", file=sys.stderr)
        return 1

    import os

    table = args.table or os.environ.get("GATEHOUSE_CASES_TABLE_NAME", "gatehouse-cases-staging")
    region = args.region or os.environ.get("GATEHOUSE_REGION", "ap-south-1")
    cutoff = int(time.time()) - args.days * 86400

    client = boto3.client("dynamodb", region_name=region)
    records: list[dict] = []
    paginator = client.get_paginator("scan")
    for page in paginator.paginate(
        TableName=table,
        ProjectionExpression=PROJECTION,
        ExpressionAttributeNames={"#v": "verdict"},
        PaginationConfig={"PageSize": 200},
    ):
        for item in page.get("Items", []):
            created_raw = item.get("created_at", {}).get("N", "0")
            if int(float(created_raw)) >= cutoff:
                records.append(item)
    print(json.dumps(records))
    return 0


if __name__ == "__main__":
    sys.exit(main())
