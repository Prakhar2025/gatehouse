"""Tests for the intake API surface (httpx ASGI, no server)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from email.message import EmailMessage
from typing import Any

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from gatehouse.api import app  # noqa: E402
from gatehouse.config import get_settings  # noqa: E402


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("GATEHOUSE_TELEGRAM_WEBHOOK_SECRET", "ci-secret")
    get_settings.cache_clear()
    return TestClient(app)


class TestHealth:
    def test_ok(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestTelegramWebhook:
    def _post(self, client: TestClient, secret: str | None = None) -> object:
        effective = "ci-secret" if secret is None else secret
        headers = {"X-Telegram-Bot-Api-Secret-Token": effective} if effective else {}
        return client.post(
            "/telegram",
            json={
                "update_id": 1,
                "message": {
                    "chat": {"id": 9},
                    "from": {"first_name": "T"},
                    "text": "hello gatehouse",
                },
            },
            headers=headers,
        )

    def test_valid_secret_accepted(self, client: TestClient) -> None:
        response = self._post(client)
        assert response.status_code == 200  # type: ignore[attr-defined]
        assert response.json()["ok"] is True  # type: ignore[attr-defined]

    def test_bad_secret_401(self, client: TestClient) -> None:
        response = self._post(client, secret="wrong")  # noqa: S106
        assert response.status_code == 401  # type: ignore[attr-defined]

    def test_missing_secret_401(self, client: TestClient) -> None:
        response = self._post(client, secret="")
        assert response.status_code == 401  # type: ignore[attr-defined]

    def test_malformed_body_401_not_500(self, client: TestClient) -> None:
        response = client.post(
            "/telegram",
            json={"nope": True},
            headers={"X-Telegram-Bot-Api-Secret-Token": "ci-secret"},
        )
        assert response.status_code in (401, 422)


@pytest.fixture()
def wa_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("GATEHOUSE_WHATSAPP_ENABLED", "true")
    monkeypatch.setenv("GATEHOUSE_WHATSAPP_APP_SECRET", "wa-app-secret")
    monkeypatch.setenv("GATEHOUSE_WHATSAPP_VERIFY_TOKEN", "wa-verify")
    get_settings.cache_clear()
    return TestClient(app)


def _wa_payload() -> dict[str, Any]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"display_phone_number": "15550001111"},
                            "contacts": [{"profile": {"name": "Riya"}}],
                            "messages": [
                                {
                                    "id": "wamid.9",
                                    "from": "919000000000",
                                    "type": "text",
                                    "text": {"body": "kyc link click"},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ]
            }
        ],
    }


class TestWhatsappWebhook:
    def test_handshake_echoes_challenge(self, wa_client: TestClient) -> None:
        response = wa_client.get(
            "/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wa-verify",
                "hub.challenge": "1158201444",
            },
        )
        assert response.status_code == 200
        assert response.json() == 1158201444

    def test_handshake_bad_token_403(self, wa_client: TestClient) -> None:
        response = wa_client.get(
            "/whatsapp",
            params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "1"},
        )
        assert response.status_code == 403

    def _signed_post(self, client: TestClient, payload: dict[str, Any], secret: str) -> Any:
        body = json.dumps(payload).encode()
        sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return client.post(
            "/whatsapp",
            content=body,
            headers={"X-Hub-Signature-256": sig, "content-type": "application/json"},
        )

    def test_disabled_flag_acks_without_processing(
        self, wa_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GATEHOUSE_WHATSAPP_ENABLED", "false")
        get_settings.cache_clear()
        response = self._signed_post(wa_client, _wa_payload(), "wa-app-secret")
        assert response.status_code == 202
        assert response.json()["queued"] is False

    def test_enabled_processes_signals(self, wa_client: TestClient) -> None:
        response = self._signed_post(wa_client, _wa_payload(), "wa-app-secret")
        assert response.status_code == 200
        assert response.json()["signals"] == 1

    def test_bad_signature_401(self, wa_client: TestClient) -> None:
        response = self._signed_post(wa_client, _wa_payload(), "wrong-secret")
        assert response.status_code == 401


def _ses_event() -> dict[str, Any]:
    msg = EmailMessage()
    msg["Subject"] = "Invoice overdue"
    msg["From"] = "fraud@example.com"
    msg["To"] = "h7k2@gatehouse.in"
    msg.set_content("Pay your overdue invoice now.")
    return {
        "Records": [
            {
                "eventSource": "aws:ses",
                "ses": {
                    "receipt": {
                        "spamVerdict": {"status": "PASS"},
                        "virusVerdict": {"status": "PASS"},
                    },
                    "mail": {
                        "messageId": "mid-9",
                        "source": "fraud@example.com",
                        "destination": ["h7k2@gatehouse.in"],
                        "commonHeaders": {"subject": "Invoice overdue"},
                        "content": base64.b64encode(msg.as_bytes()).decode(),
                    },
                },
            }
        ]
    }


@pytest.fixture()
def email_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("GATEHOUSE_EMAIL_ALIAS_ALLOWLIST", "h7k2,k9m4")
    get_settings.cache_clear()
    return TestClient(app)


class TestEmailIntake:
    def test_bound_alias_accepted(self, email_client: TestClient) -> None:
        response = email_client.post("/email", json=_ses_event())
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["event_id"].startswith("email#")

    def test_unknown_alias_404(self, email_client: TestClient) -> None:
        event = _ses_event()
        event["Records"][0]["ses"]["mail"]["destination"] = ["zzzz@gatehouse.in"]
        response = email_client.post("/email", json=event)
        assert response.status_code == 404

    def test_malformed_event_400(self, email_client: TestClient) -> None:
        response = email_client.post("/email", json={"nope": True})
        assert response.status_code == 400
