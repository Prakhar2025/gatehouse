"""Lambda handler: Telegram webhook -> full investigation -> persistence.

Deployment shape (docs/09 section 2):
- API Gateway HTTP API -> this handler (Mangum adapter over the FastAPI app)
- Bedrock invoked in-region via the routing table (doc 03 section 8.1)
- Spend meter enforced per case; breaker counters live in DynamoDB (P4+)

Cold-start discipline: settings and clients are cached at module scope so warm
invocations reuse them. Secrets arrive via environment (SSM at deploy time).
"""

from __future__ import annotations

import json
import os
from typing import Any

from mangum import Mangum

from gatehouse.api import app

# Mangum wraps ASGI for Lambda; API Gateway HTTP API payload v2.
handler = Mangum(app, lifespan="off", api_gateway_base_path="/")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Direct Lambda entry for webhook events (non-HTTP API deployments).

    Kept alongside the Mangum handler so SAM can switch route styles without
    code changes. Verifies the Telegram secret before any parsing.
    """
    from gatehouse.channels.telegram import (
        WebhookError,
        build_reply_verdict,
        parse_update,
        verify_secret,
    )
    from gatehouse.config import get_settings

    settings = get_settings()
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    try:
        verify_secret(headers.get("x-telegram-bot-api-secret-token"), settings)
        body = json.loads(event.get("body") or "{}")
        # Parse validates the update shape; the signal object is consumed by
        # the async investigation path wired in P4.
        parse_update(body)
    except (WebhookError, json.JSONDecodeError) as exc:
        return {"statusCode": 401, "body": json.dumps({"error": str(exc)})}

    # Full investigation runs here in P4's async path; the intake contract and
    # reply tone are already production code (tested), verdict is placeholder
    # until Bedrock wiring is enabled by the deploy flag.
    reply = build_reply_verdict("SUSPICIOUS", ["INTAKE_ACK"])
    return {"statusCode": 200, "body": json.dumps({"ok": True, "reply": reply})}
