"""Lambda handler: Telegram webhook -> full investigation -> persistence.

Deployment shape (docs/09 section 2):
- API Gateway HTTP API -> this handler (Mangum adapter over the FastAPI app)
- Bedrock invoked in-region via the routing table (doc 03 section 8.1)
- Spend meter enforced per case; breaker counters live in DynamoDB (P4+)

Cold-start discipline: settings, stores, and clients are cached at module scope
so warm invocations reuse them (see gatehouse.runtime). Secrets arrive via
environment (SSM at deploy time).
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from mangum import Mangum

from gatehouse.api import app

# Mangum wraps ASGI for Lambda; API Gateway HTTP API payload v2.
_mangum = Mangum(app, lifespan="off", api_gateway_base_path="/")


def _strip_stage_prefix(event: dict[str, Any]) -> dict[str, Any]:
    """Remove the stage segment from the request path for named HTTP stages.

    A named stage (e.g. staging) delivers /staging/health while routes are
    registered at /health. Mangum resolves the ASGI path from
    requestContext.http.path, so both that field and rawPath are rewritten.
    The stage name equals the deployment environment; local dev servers are
    unaffected because they never carry the prefix.
    """
    stage = os.environ.get("GATEHOUSE_ENVIRONMENT", "")
    if not stage:
        return event
    prefix = f"/{stage}"
    raw_path = event.get("rawPath")
    if isinstance(raw_path, str):
        if raw_path == prefix:
            event["rawPath"] = "/"
        elif raw_path.startswith(prefix + "/"):
            event["rawPath"] = raw_path[len(prefix) :]
    ctx = event.get("requestContext")
    http = ctx.get("http") if isinstance(ctx, dict) else None
    if isinstance(http, dict):
        path = http.get("path")
        if isinstance(path, str):
            if path == prefix:
                http["path"] = "/"
            elif path.startswith(prefix + "/"):
                http["path"] = path[len(prefix) :]
    return event


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """HTTP API entrypoint with stage-aware path resolution."""
    return _mangum(_strip_stage_prefix(event), context)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _response(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {"statusCode": status, "body": json.dumps(body)}


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Direct Lambda entry for webhook events (non-HTTP API deployments).

    Kept alongside the Mangum handler so SAM can switch route styles without
    code changes. Verifies the Telegram secret before any parsing, then runs
    the live loop synchronously inside the invocation budget.
    """
    from gatehouse.channels.telegram import (
        WebhookError,
        parse_update,
        verify_secret,
    )
    from gatehouse.config import get_settings
    from gatehouse.runtime import handle_telegram_signal

    settings = get_settings()
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    try:
        verify_secret(headers.get("x-telegram-bot-api-secret-token"), settings)
        body = json.loads(event.get("body") or "{}")
        signal = parse_update(body)
    except (WebhookError, json.JSONDecodeError) as exc:
        return _response(401, {"error": str(exc)})

    outcome = asyncio.run(handle_telegram_signal(signal))
    # Always 200 post-verification: Telegram retries non-2xx deliveries and
    # refusal is an answer, not a transport failure.
    return _response(
        200,
        {
            "ok": True,
            "reply": outcome.reply_text,
            "status": outcome.status,
            "case_id": outcome.case_id,
        },
    )
