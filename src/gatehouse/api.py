"""Gatehouse intake API: the single webhook surface (doc 09 section 2).

One FastAPI app, deployed to Lambda via SAM (P4). Every route:
- verifies Telegram's secret header before touching the body,
- never logs raw content (scrubbed logging only),
- returns fast: investigation runs async inside the request budget.

Local dev: uvicorn gatehouse.api:app --port 8080
"""

from __future__ import annotations

import sys
import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from gatehouse.channels.email import EmailIntakeError, parse_receipt_event
from gatehouse.channels.events import GatewayEvent, build_envelope, content_hash
from gatehouse.channels.telegram import (
    WebhookError,
    build_reply_verdict,
    parse_update,
    verify_secret,
)
from gatehouse.channels.whatsapp import (
    WhatsAppWebhookError,
    parse_verification,
    parse_webhook,
    verify_signature,
    verify_subscription_token,
)
from gatehouse.channels.whatsapp import (
    build_reply as whatsapp_reply,
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


@app.get("/whatsapp")
async def whatsapp_verify(request: Request) -> JSONResponse:
    """Meta subscription handshake (GET). Token check before any echo."""
    settings = get_settings()
    params = request.query_params
    try:
        verify_subscription_token(params.get("hub.verify_token"), settings)
        challenge = parse_verification(
            {
                "hub.mode": params.get("hub.mode"),
                "hub.verify_token": params.get("hub.verify_token"),
                "hub.challenge": params.get("hub.challenge"),
            }
        )
    except WhatsAppWebhookError as exc:
        log.warning("whatsapp_verify_rejected", extra={"extra_fields": {"reason": str(exc)}})
        return JSONResponse(status_code=403, content={"error": "rejected"})
    return JSONResponse(
        status_code=200, content=int(challenge) if challenge.isdigit() else challenge
    )


@app.post("/whatsapp")
async def whatsapp_webhook(request: Request) -> JSONResponse:
    """Meta Cloud API intake. Flag-gated: disabled means verify-only."""
    settings = get_settings()
    raw = await request.body() if hasattr(request, "body") else b""
    try:
        payload: dict[str, Any] = await request.json()
        verify_signature(request.headers.get("X-Hub-Signature-256"), raw, settings)
    except (WhatsAppWebhookError, ValueError) as exc:
        log.warning("whatsapp_rejected", extra={"extra_fields": {"reason": str(exc)}})
        return JSONResponse(status_code=401, content={"error": "rejected"})
    if not settings.whatsapp_enabled:
        log.info(
            "whatsapp_disabled_ack", extra={"extra_fields": {"object": str(payload.get("object"))}}
        )
        return JSONResponse(status_code=202, content={"ok": True, "queued": False})
    try:
        signals = parse_webhook(payload)
    except WhatsAppWebhookError as exc:
        log.warning("whatsapp_malformed", extra={"extra_fields": {"reason": str(exc)}})
        return JSONResponse(status_code=400, content={"error": "malformed"})
    for signal in signals:
        log.info(
            "signal_accepted",
            extra={
                "extra_fields": {
                    "channel": "whatsapp",
                    "message_id": signal.message_id,
                    "has_media": signal.has_media,
                    "length": len(signal.text),
                }
            },
        )
    reply = whatsapp_reply("SUSPICIOUS")  # placeholder verdict path
    return JSONResponse(
        status_code=200, content={"ok": True, "signals": len(signals), "reply": reply}
    )


@app.post("/email")
async def email_intake(request: Request) -> JSONResponse:
    """SES receipt-rule target. Invocation authenticity is SES's own boundary."""
    settings = get_settings()
    try:
        event: dict[str, Any] = await request.json()
        signal = parse_receipt_event(event)
    except EmailIntakeError as exc:
        log.warning("email_rejected", extra={"extra_fields": {"reason": str(exc)}})
        return JSONResponse(status_code=400, content={"error": "rejected"})

    envelope = build_envelope(
        GatewayEvent(
            channel="email",
            household_id=f"alias:{signal.recipient_alias}",
            sender_name=signal.sender,
            text=signal.text,
            is_forward=False,
            received_at=time.time(),
        )
    )
    allowed_aliases = {
        a.strip().lower() for a in settings.email_alias_allowlist.split(",") if a.strip()
    }
    if signal.recipient_alias not in allowed_aliases:
        log.warning("email_unknown_alias", extra={"extra_fields": {"reason": "alias_not_bound"}})
        return JSONResponse(status_code=404, content={"error": "unknown alias"})
    log.info(
        "signal_accepted",
        extra={
            "extra_fields": {
                "channel": "email",
                "message_id": signal.message_id,
                "event_id_hash": content_hash(envelope["event_id"]),
            }
        },
    )
    return JSONResponse(status_code=200, content={"ok": True, "event_id": envelope["event_id"]})


def main() -> int:
    """Local dev entrypoint."""
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8080)
    return 0


if __name__ == "__main__":
    sys.exit(main())
