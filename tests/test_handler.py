"""Tests for the Lambda handler (direct invoke path, no AWS)."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from gatehouse.config import get_settings


@pytest.fixture()
def _secret(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("GATEHOUSE_TELEGRAM_WEBHOOK_SECRET", "lambda-secret")
    get_settings.cache_clear()
    yield
    monkeypatch.delenv("GATEHOUSE_TELEGRAM_WEBHOOK_SECRET")
    get_settings.cache_clear()


def _event(
    hdr_value: str | None = "lambda-secret", body: dict[str, object] | None = None
) -> dict[str, object]:
    return {
        "headers": (
            {"X-Telegram-Bot-Api-Secret-Token": hdr_value} if hdr_value is not None else {}
        ),
        "body": json.dumps(
            body
            or {
                "update_id": 7,
                "message": {
                    "chat": {"id": 42},
                    "from": {"first_name": "P"},
                    "text": "is this a scam?",
                },
            }
        ),
    }


class TestHandler:
    def test_valid_secret_returns_ack(self, _secret: None) -> None:
        from gatehouse.handler import lambda_handler

        response = lambda_handler(_event(), None)
        assert response["statusCode"] == 200
        payload = json.loads(response["body"])
        assert payload["ok"] is True

    def test_bad_secret_rejected(self, _secret: None) -> None:
        from gatehouse.handler import lambda_handler

        response = lambda_handler(_event(hdr_value="nope"), None)
        assert response["statusCode"] == 401

    def test_missing_secret_rejected(self, _secret: None) -> None:
        from gatehouse.handler import lambda_handler

        response = lambda_handler(_event(hdr_value=None), None)
        assert response["statusCode"] == 401

    def test_malformed_body_rejected(self, _secret: None) -> None:
        from gatehouse.handler import lambda_handler

        response = lambda_handler(_event(body={"nope": 1}), None)
        assert response["statusCode"] == 401
