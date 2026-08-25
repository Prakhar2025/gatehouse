"""Gatehouse intake API: the single webhook surface (doc 09 section 2).

One FastAPI app, deployed to Lambda via SAM (P4). Every route:
- verifies Telegram's secret header before touching the body,
- never logs raw content (scrubbed logging only),
- returns fast: investigation runs async inside the request budget.

Local dev: uvicorn gatehouse.api:app --port 8080
"""

from __future__ import annotations

import sys
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from gatehouse.channels.telegram import (
    WebhookError,
    build_reply_verdict,
    parse_update,
    verify_secret,
)
from gatehouse.config import get_settings
from gatehouse.logging_utils import configure_logging, get_logger

configure_logging()
log = get_logger("gatehouse.api")

app = FastAPI(title="Gatehouse", version="0.1.0", docs_url=None, redoc_url=None)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness for ALB/Lambda probes. Says nothing about internals."""
    return {"status": "ok"}


@app.post("/telegram")
async def telegram_webhook(request: Request) -> JSONResponse:
    settings = get_settings()
    try:
        verify_secret(request.headers.get("X-Telegram-Bot-Api-Secret-Token"), settings)
        payload: dict[str, Any] = await request.json()
        signal = parse_update(payload)
    except WebhookError as exc:
        log.warning("webhook_rejected", extra={"extra_fields": {"reason": str(exc)}})
        return JSONResponse(status_code=401, content={"error": "rejected"})

    # Pipeline invocation is wired in the deployment layer (P4); the intake
    # contract is fully validated here so the wire format is frozen early.
    log.info(
        "signal_accepted",
        extra={
            "extra_fields": {
                "update_id": signal.update_id,
                "chat_id": signal.chat_id,
                "is_forward": signal.is_forward,
                "length": len(signal.text),
            }
        },
    )
    reply = build_reply_verdict("SUSPICIOUS", ["INTAKE_ACK"])  # placeholder verdict path
    return JSONResponse(status_code=200, content={"ok": True, "reply": reply})


def main() -> int:
    """Local dev entrypoint."""
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8080)
    return 0


if __name__ == "__main__":
    sys.exit(main())
