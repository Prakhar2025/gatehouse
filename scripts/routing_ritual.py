"""Model routing verification ritual (doc 03 section 8, P4 exit requirement).

One capped invocation per candidate model ID in the deploy region, results
printed as a markdown-ready table. Charter budget rules honored: one-shot,
maxTokens capped at 16, seeded fixed prompt, nothing written to storage.
Titan Embeddings is probed through InvokeModel (not converse-shaped).

Usage:
    python scripts/routing_ritual.py
"""

from __future__ import annotations

import json
import time
from typing import Any

import boto3

REGION = "ap-south-1"
MAX_TOKENS = 16
PROMPT = "Reply with the single word: ok"

TEXT_MODELS: list[tuple[str, str]] = [
    ("TRIAGE primary", "apac.amazon.nova-micro-v1:0"),
    ("ENGAGE/NARRATIVE primary", "apac.amazon.nova-lite-v1:0"),
    ("VERIFY primary", "apac.amazon.nova-pro-v1:0"),
    ("FALLBACK narrative", "openai.gpt-oss-120b-1:0"),
    ("FALLBACK verify", "us.meta.llama3-3-70b-instruct-v1:0"),
    ("degraded-mode classifier", "zai.glm-4.7-flash"),
    ("candidate revisit", "amazon.nova-2-lite-v1:0"),
    ("candidate access check", "anthropic.claude-haiku-4-5"),
]


def _probe_text(br: Any, role: str, model_id: str) -> None:
    started = time.time()
    try:
        resp = br.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": PROMPT}]}],
            inferenceConfig={"maxTokens": MAX_TOKENS},
        )
        ms = int((time.time() - started) * 1000)
        blocks = resp["output"]["message"]["content"]
        usage = resp.get("usage", {})
        # Reasoning models (gpt-oss family) may return no visible text block
        # under a tight output budget; the invocation itself succeeding is
        # what this ritual verifies (doc 03 section 8.1 note).
        text = next((b.get("text", "").strip() for b in blocks if "text" in b), "")
        detail = f"reply={text[:14]}" if text else "invoked-ok; visible text empty at maxTokens=16"
        print(
            f"| {role} | `{model_id}` | PASS | {ms}ms | "
            f"in={usage.get('inputTokens')} out={usage.get('outputTokens')} | {detail} |"
        )
    except Exception as exc:
        ms = int((time.time() - started) * 1000)
        first = str(exc).replace("\n", " ")[:130]
        print(f"| {role} | `{model_id}` | FAIL | {ms}ms | {type(exc).__name__}: {first} |")


def _probe_embed(br: Any) -> None:
    started = time.time()
    try:
        resp = br.invoke_model(
            modelId="amazon.titan-embed-text-v2:0",
            body=json.dumps({"inputText": PROMPT}),
        )
        ms = int((time.time() - started) * 1000)
        body = json.loads(resp["body"].read())
        dims = len(body.get("embedding", []))
        print(
            f"| claim embeddings | `amazon.titan-embed-text-v2:0` | PASS | {ms}ms | dims={dims} |"
        )
    except Exception as exc:
        ms = int((time.time() - started) * 1000)
        first = str(exc).split(".")[0][:80]
        print(
            f"| claim embeddings | `amazon.titan-embed-text-v2:0` | FAIL | {ms}ms | "
            f"{type(exc).__name__}: {first} |"
        )


def main() -> int:
    br = boto3.client("bedrock-runtime", region_name=REGION)
    print(f"Routing ritual {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} region={REGION}")
    print("| Role | Model ID | Result | Latency | Detail |")
    print("|---|---|---|---|---|")
    for role, model_id in TEXT_MODELS:
        _probe_text(br, role, model_id)
    _probe_embed(br)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
