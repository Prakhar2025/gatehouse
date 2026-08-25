"""Telegram outbound transport: guardian cards and member replies.

Transport only: it sends exactly the text it is given and reports success as a
boolean. Formatting lives in notify (guardian cards) and channels.telegram
(member replies), per doc 05 section 6. Uses stdlib urllib so Lambda needs no
extra HTTP dependency for the reply path.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from gatehouse.logging_utils import get_logger

log = get_logger("gatehouse.runtime_telegram")

_API_BASE = "https://api.telegram.org"
_TIMEOUT_S = 8.0


class TelegramSender:
    """Prod notifier backend behind the Notifier protocol."""

    def __init__(self, bot_token: str) -> None:
        self._token = bot_token

    def send(self, chat_id: str, text: str) -> bool:
        """One sendMessage attempt. False means the caller should fall back."""
        return send_reply(self._token, chat_id, text)


def send_reply(bot_token: str, chat_id: str, text: str) -> bool:
    """Send one text message; True only on Telegram's ok:true response."""
    if not bot_token or not chat_id or not text:
        return False
    url = f"{_API_BASE}/bot{bot_token}/sendMessage"
    payload = json.dumps(
        {"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": True}
    ).encode("utf-8")
    req = urllib.request.Request(  # noqa: S310 - fixed https API host
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:  # noqa: S310
            body: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        return bool(body.get("ok"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        log.warning("telegram_send_failed", extra={"extra_fields": {"error": type(exc).__name__}})
        return False


def set_webhook(bot_token: str, url: str, secret_token: str) -> dict[str, Any]:
    """Register the webhook with Telegram's secret-token header contract."""
    full = f"{_API_BASE}/bot{bot_token}/setWebhook"
    payload = json.dumps({"url": url, "secret_token": secret_token}).encode("utf-8")
    req = urllib.request.Request(  # noqa: S310
        full,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:  # noqa: S310
        return dict(json.loads(resp.read().decode("utf-8")))


def get_webhook_info(bot_token: str) -> dict[str, Any]:
    """Read back webhook state; used to verify the live binding."""
    full = f"{_API_BASE}/bot{bot_token}/getWebhookInfo"
    req = urllib.request.Request(full, method="GET")  # noqa: S310
    with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:  # noqa: S310
        return dict(json.loads(resp.read().decode("utf-8")))
