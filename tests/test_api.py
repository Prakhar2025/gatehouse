"""Tests for the intake API surface (httpx ASGI, no server)."""

from __future__ import annotations

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
