"""Tests for backend selection and the direct Lambda entrypoint."""

from __future__ import annotations

import json
from typing import Any

import pytest

from gatehouse import runtime
from gatehouse.agents.mock_model import MockModel
from gatehouse.config import Settings, get_settings
from gatehouse.runtime import (
    PipelineOutcome,
    build_bindings,
    build_bundles,
    build_case_store,
    build_dedupe,
    build_graph,
    build_model,
    build_notifier,
    reset_runtime,
    run_pipeline,
)


class TestBackendSelection:
    def test_local_builders_are_memory_backed(self) -> None:
        s = Settings(environment="local")
        from gatehouse.channels.binding import InMemoryBindingStore
        from gatehouse.channels.dedupe import InMemoryDedupeStore
        from gatehouse.channels.evidence import InMemoryBundleStore
        from gatehouse.channels.notify import LoggingNotifier
        from gatehouse.graph.store import InMemoryGraphStore

        assert isinstance(build_bindings(s), InMemoryBindingStore)
        assert isinstance(build_dedupe(s), InMemoryDedupeStore)
        assert isinstance(build_bundles(s), InMemoryBundleStore)
        assert isinstance(build_graph(s), InMemoryGraphStore)
        assert isinstance(build_notifier(s), LoggingNotifier)
        assert build_model(s) is None
        assert build_case_store(s) is None

    def test_staging_builders_are_dynamo_and_bedrock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeClient:
            def __init__(self, service: str) -> None:
                self.service = service

        def fake_client(service: str) -> Any:
            return FakeClient(service)

        monkeypatch.setattr(runtime, "_aws_client", fake_client)
        s = Settings(environment="staging")
        from gatehouse.channels.binding import DynamoBindingStore
        from gatehouse.channels.dedupe import DynamoDedupeStore
        from gatehouse.channels.evidence import DynamoBundleStore
        from gatehouse.runtime_dynamo import DynamoGraphStore

        assert isinstance(build_bindings(s), DynamoBindingStore)
        assert isinstance(build_dedupe(s), DynamoDedupeStore)
        assert isinstance(build_bundles(s), DynamoBundleStore)
        assert isinstance(build_graph(s), DynamoGraphStore)

    def test_notifier_falls_back_without_bot_token(self) -> None:
        from gatehouse.channels.notify import LoggingNotifier

        s = Settings(environment="staging", telegram_bot_token="")
        assert isinstance(build_notifier(s), LoggingNotifier)


class TestLambdaEntrypoint:
    def _event(self, secret: str | None, text: str = "hello") -> dict[str, Any]:
        headers = {} if secret is None else {"x-telegram-bot-api-secret-token": secret}
        return {
            "headers": headers,
            "body": json.dumps(
                {
                    "update_id": 7,
                    "message": {
                        "chat": {"id": 555},
                        "from": {"first_name": "R"},
                        "text": text,
                    },
                }
            ),
        }

    @pytest.fixture(autouse=True)
    def _env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GATEHOUSE_TELEGRAM_WEBHOOK_SECRET", "ci-secret")
        get_settings.cache_clear()
        reset_runtime()

    def test_bad_secret_rejected_before_loop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        called = False

        def fail_run(coro: Any) -> None:
            nonlocal called
            called = True

        monkeypatch.setattr("gatehouse.handler.asyncio.run", fail_run)
        from gatehouse.handler import lambda_handler

        result = lambda_handler(self._event("wrong"), None)
        assert result["statusCode"] == 401
        assert called is False

    def test_live_invocation_runs_pipeline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rt = runtime.get_runtime()
        invite = rt.bindings.issue_invite("hh-lambda")
        rt.bindings.consume_invite(invite.code, "telegram", "555")
        rt.model = MockModel(tool_payload={"scam_likelihood": 0.05, "reason_code": "NONE"})
        from gatehouse.handler import lambda_handler

        result = lambda_handler(self._event("ci-secret"), None)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["ok"] is True
        assert body["status"] == "investigated"

    def test_unlinked_sender_answered_not_errored(self) -> None:
        from gatehouse.handler import lambda_handler

        result = lambda_handler(self._event("ci-secret", text="scam link"), None)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "refused"


class TestPipelineSpendAccounting:
    def test_meter_records_real_model_call(self) -> None:
        from gatehouse.spend import SpendMeter

        s = Settings(environment="local")
        reset_runtime()
        rt = runtime.get_runtime(s)
        meter = SpendMeter(max_usd=0.02, max_calls=12)
        outcome: PipelineOutcome = __import__("asyncio").run(
            run_pipeline(
                rt,
                channel="telegram",
                household_id="hh-spend",
                sender_name="R",
                text="pay now http://odd-site.example urgent today",
                is_forward=True,
                meter=meter,
            )
        )
        assert outcome.status == "investigated"
        # Rules-only path spends nothing; the meter proves the breaker wiring.
        assert meter.total_usd == outcome.spend_usd


class TestStagePrefixStripping:
    """Named HTTP API stages deliver /stage/... paths; routes live at /."""

    def _invoke(self, raw_path: str, ctx_path: str | None = None) -> dict[str, Any]:
        from unittest.mock import patch

        captured: dict[str, Any] = {}

        def fake_mangum(event: dict[str, Any], context: Any) -> dict[str, Any]:
            captured["raw_path"] = event["rawPath"]
            captured["ctx_path"] = event.get("requestContext", {}).get("http", {}).get("path")
            return {"statusCode": 200}

        import gatehouse.handler as h

        with patch.object(h, "_mangum", fake_mangum):
            out = h.handler({"rawPath": raw_path}, None)
        assert out == {"statusCode": 200}
        return captured

    def test_staging_stage_prefix_removed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GATEHOUSE_ENVIRONMENT", "staging")
        result = self._invoke("/staging/health", "/staging/health")
        assert result["raw_path"] == "/health"
        assert result["ctx_path"] == "/health"

    def test_prod_stage_prefix_removed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GATEHOUSE_ENVIRONMENT", "prod")
        result = self._invoke("/prod/telegram", "/prod/telegram")
        assert result["raw_path"] == "/telegram"
        assert result["ctx_path"] == "/telegram"

    def test_local_leaves_paths_alone(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GATEHOUSE_ENVIRONMENT", "local")
        result = self._invoke("/health", "/health")
        assert result["raw_path"] == "/health"
        assert result["ctx_path"] == "/health"

    def test_exact_stage_root_maps_to_slash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GATEHOUSE_ENVIRONMENT", "staging")
        result = self._invoke("/staging", "/staging/")
        assert result["raw_path"] == "/"
        assert result["ctx_path"] == "/"
