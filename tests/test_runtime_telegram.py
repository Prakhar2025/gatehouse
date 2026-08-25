"""Tests for the Telegram outbound transport and the digest Lambda."""

from __future__ import annotations

import io
import json
import urllib.error
from typing import Any

from gatehouse.digest import handler as digest_handler
from gatehouse.runtime_telegram import TelegramSender, get_webhook_info, send_reply, set_webhook

urllib_request = __import__("urllib.request", fromlist=["urlopen"])  # stdlib, patched in tests


class FakeResponse(io.BytesIO):
    """BytesIO with context-manager close, enough for urlopen's return."""


def _patch_urlopen(monkeypatch: Any, payload: dict[str, Any] | Exception) -> list[dict[str, Any]]:
    captured: list[dict[str, Any]] = []

    def fake_urlopen(req: Any, timeout: float = 0) -> FakeResponse:
        body = json.loads(req.data.decode("utf-8")) if req.data else {}
        captured.append({"url": req.full_url, "data": body, "method": req.method})
        if isinstance(payload, Exception):
            raise payload
        return FakeResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(urllib_request, "urlopen", fake_urlopen)
    return captured


class TestSendReply:
    def test_ok_response_true(self, monkeypatch: Any) -> None:
        captured = _patch_urlopen(monkeypatch, {"ok": True, "result": {}})
        assert send_reply("tok", "123", "hello") is True
        assert "api.telegram.org/bottok/sendMessage" in captured[0]["url"]
        assert captured[0]["data"]["chat_id"] == "123"

    def test_error_response_false(self, monkeypatch: Any) -> None:
        _patch_urlopen(monkeypatch, {"ok": False, "description": "chat not found"})
        assert send_reply("tok", "123", "hello") is False

    def test_network_failure_false_not_raise(self, monkeypatch: Any) -> None:
        _patch_urlopen(monkeypatch, urllib.error.URLError("no route"))
        assert send_reply("tok", "123", "hello") is False

    def test_empty_args_never_call_network(self, monkeypatch: Any) -> None:
        captured = _patch_urlopen(monkeypatch, {"ok": True})
        assert send_reply("", "", "") is False
        assert captured == []

    def test_sender_protocol_delegates(self, monkeypatch: Any) -> None:
        captured = _patch_urlopen(monkeypatch, {"ok": True})
        sender = TelegramSender("tok")
        assert sender.send("42", "card text") is True
        assert captured[0]["data"]["text"] == "card text"


class TestWebhookManagement:
    def test_set_webhook_posts_url_and_secret(self, monkeypatch: Any) -> None:
        captured = _patch_urlopen(monkeypatch, {"ok": True})
        hdr_value = "s3cret-value"
        out = set_webhook("tok", "https://x.example/tg", hdr_value)
        assert out["ok"] is True
        body = captured[0]["data"]
        assert body["url"] == "https://x.example/tg"
        assert body["secret_token"] == hdr_value

    def test_get_webhook_info_get(self, monkeypatch: Any) -> None:
        captured = _patch_urlopen(monkeypatch, {"ok": True, "result": {"pending_update_count": 0}})
        out = get_webhook_info("tok")
        assert out["result"]["pending_update_count"] == 0
        assert captured[0]["method"] == "GET"


class TestDigestHandler:
    def test_returns_flushed_count_shape(self, monkeypatch: Any) -> None:
        from gatehouse.config import get_settings
        from gatehouse.runtime import reset_runtime

        monkeypatch.setenv("GATEHOUSE_TELEGRAM_WEBHOOK_SECRET", "ci-secret")
        get_settings.cache_clear()
        reset_runtime()
        result = digest_handler({}, None)
        assert result["statusCode"] == 200
        assert json.loads(result["body"])["flushed"] == 0
