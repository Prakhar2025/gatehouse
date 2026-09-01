"""Chaos suite: doc 03 failure matrix rows 1-7 as executable guarantees.

Each test injects the real fault class into one dependency and asserts the
defined degraded behavior: explicit flags on the result, no crash to the
caller, and never a silent SAFE when verification was lost. Row 8 (pack
manifest invalid) is enforced by CI's validate_packs step and the loader's
fail-fast PackError, so it lives outside this runtime suite.
"""

from __future__ import annotations

import asyncio
import calendar
from pathlib import Path
from typing import Any

import pytest

from gatehouse.agents.mock_model import MockModel
from gatehouse.channels.dedupe import InMemoryDedupeStore
from gatehouse.config import Settings
from gatehouse.graph.store import InMemoryGraphStore
from gatehouse.orchestrator import investigate
from gatehouse.packs.loader import load_pack

REPO = Path(__file__).resolve().parents[1]
PACK = REPO / "packs" / "in" / "pack.yaml"

# 2026-06-15 06:30 UTC is 12:00 IST: comfortably outside quiet hours, and
# pinned so notification tests never depend on the wall clock (what-broke:
# the hour-of-day test trap).
NOON_IST_EPOCH = calendar.timegm((2026, 6, 15, 6, 30, 0, 0, 0, 0))


def go(coro: Any) -> Any:
    return asyncio.run(coro)


class _Boom(Exception):
    """The dependency is on fire."""


class _ExplodingTriageModel:
    """Row 1: the triage LLM raises mid-call."""

    def get_config(self) -> dict[str, Any]:
        return {"model_id": "chaos.nova-micro-v1:0"}

    async def structured_output(self, *_args: Any, **_kwargs: Any) -> Any:
        # Async-generator shape so the consumer's `async for` attaches before
        # the fault hits mid-stream, like a real model dying between events.
        yield {}
        raise _Boom("triage model unavailable")


class _DeadStore(InMemoryGraphStore):
    """Row 3: every graph store operation raises."""

    def upsert_event(self, *args: Any, **kwargs: Any) -> None:
        raise _Boom("graph store down")

    def query(self, *args: Any, **kwargs: Any) -> list[Any]:
        raise _Boom("graph store down")

    def finding_for(self, *args: Any, **kwargs: Any) -> Any:
        raise _Boom("graph store down")


class _DedupeOutage(InMemoryDedupeStore):
    """Row 6 shape: dedupe writes fail."""

    def check_and_record(self, *args: Any, **kwargs: Any) -> None:
        raise _Boom("dedupe table throttling")


def _investigate(text: str, **kwargs: Any) -> Any:
    settings = kwargs.pop("settings", None) or Settings(environment="local")
    return go(
        investigate(
            "case-chaos",
            text,
            load_pack(PACK),
            kwargs.pop("store", None) or InMemoryGraphStore(),
            settings=settings,
            **kwargs,
        )
    )


def _verify_boom(monkeypatch: pytest.MonkeyPatch) -> None:
    import gatehouse.orchestrator as orch

    def boom(*args: Any, **kwargs: Any) -> Any:
        raise _Boom("verify rules exploded")

    monkeypatch.setattr(orch, "verify_signal", boom)


class TestRow1TriageLLMDown:
    def test_rules_only_result_with_loud_flag(self) -> None:
        text = "SBI KYC expired, pay now at http://sbi-verify.top UTR123456789012"
        result = _investigate(text, model=_ExplodingTriageModel())
        assert result.verdict in ("SCAM", "SUSPICIOUS")
        assert result.triage_result is not None
        assert result.triage_result.reason_code.startswith("model_error:")
        assert "TRIAGE_MODEL_FALLBACK" in result.degraded_flags

    def test_no_crash_on_benign_text(self) -> None:
        result = _investigate("lunch tomorrow?", model=_ExplodingTriageModel())
        assert result.verdict == "SAFE"


class TestRow2VerifyLost:
    def test_verify_fault_forces_needs_human_not_safe(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _verify_boom(monkeypatch)
        result = _investigate("totally innocent lunch plans")
        assert result.verdict == "NEEDS_HUMAN"
        assert "VERIFICATION_UNAVAILABLE" in result.reason_codes
        assert "VERIFY_UNAVAILABLE" in result.degraded_flags

    def test_needs_human_survives_model_leg(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _verify_boom(monkeypatch)
        result = _investigate(
            "pay now to scammer99@ybl",
            model=MockModel(tool_payload={"scam_likelihood": 0.9, "reason_code": "X"}),
        )
        assert result.verdict == "NEEDS_HUMAN"
        assert result.triage_result is not None
        assert result.spend_usd >= 0.0


class TestRow3GraphStoreDown:
    def test_graph_unavailable_finding_case_continues(self) -> None:
        # The fixture must carry an identifier the conservative extraction
        # grammar accepts (a phone here). URLs are deliberately not extracted,
        # so a URL-bearing signal reaches the empty branch and can never
        # exercise the outage path.
        text = "Pay 50000 immediately to agent 9876501234 or account freezes"
        result = _investigate(text, store=_DeadStore())
        assert result.graph_finding is not None
        assert result.graph_finding.unavailable is True
        pkg = result.package
        assert pkg is not None
        assert "GRAPH_UNAVAILABLE" in pkg.degraded_flags
        # The case still completes with a defensible verdict from surviving
        # evidence; weaker graph input never inflates confidence.
        assert result.verdict in ("SCAM", "SUSPICIOUS", "SAFE")

    def test_empty_result_is_not_an_outage(self) -> None:
        """A signal without correlatable identifiers produces a normal empty
        finding. Marking it unavailable polluted degraded-mode statistics and
        mislabeled healthy traffic as an outage in every soak report."""
        result = _investigate("sharing the saturday family dinner photos", store=_DeadStore())
        assert result.graph_finding.unavailable is False
        pkg = result.package
        assert pkg is not None
        assert "GRAPH_UNAVAILABLE" not in pkg.degraded_flags

    def test_dead_store_is_actually_exercised(self) -> None:
        """An identifier-bearing message reaches the dead store and still
        completes: the defined row-3 behavior is continuation with the
        GRAPH_UNAVAILABLE disclosure on every outcome band."""
        text = "Your KYC has expired, pay now to scammer99@ybl"
        result = _investigate(text, store=_DeadStore())
        assert result.graph_finding is not None
        assert result.graph_finding.unavailable is True
        pkg = result.package
        assert pkg is not None
        assert "GRAPH_UNAVAILABLE" in pkg.degraded_flags
        assert result.verdict in ("SCAM", "SUSPICIOUS", "NEEDS_HUMAN", "SAFE")


class _DeadEngageChannel:
    """Row 4: the engagement transport is unreachable."""

    def deliver(self, contact: str, text: str) -> bool:
        return False

    def receive(self, contact: str) -> None:
        return None


class TestRow4EngageChannelError:
    def test_channel_error_yields_no_response_outcome(self) -> None:
        from gatehouse.agents.engage import run_engagement

        out = go(run_engagement("case-e", "scammer@ybl", "confirm intent", _DeadEngageChannel()))
        # Engagement skipped with a defined outcome, never an exception.
        assert out.outcome == "NO_RESPONSE"
        assert out.turns_used == 0
        assert out.reason_code == "opener_delivery_failed"

    def test_budget_refusal_is_defined_and_flagged(self) -> None:
        from gatehouse.agents.engage import run_engagement
        from gatehouse.spend import SpendMeter

        meter = SpendMeter(max_usd=0.0, max_calls=1)
        out = go(
            run_engagement(
                "case-e2", "scammer@ybl", "confirm intent", _DeadEngageChannel(), meter=meter
            )
        )
        assert out.outcome == "BUDGET_REFUSED"
        assert "ENGAGE_BUDGET_REFUSED" in out.degraded_flags


class TestRow5TelegramOutage:
    def test_failed_decision_send_queues_into_digest(self) -> None:
        from gatehouse.channels.notify import EscalationCard, LoggingNotifier, NotificationService

        class _DownNotifier(LoggingNotifier):
            def send(self, chat_id: str, text: str) -> bool:
                return False  # Telegram unreachable

        svc = NotificationService(_DownNotifier())
        card = EscalationCard(
            household_id="hh",
            case_id="c1",
            urgency="DECISION",
            title="SUSPICIOUS on a telegram forward",
            summary="see bundle",
        )
        s = Settings(environment="local", guardian_telegram_chat_id="12345")
        outcome = svc.escalate(card, s, now=NOON_IST_EPOCH)
        assert outcome == "queued"
        assert len(svc.digest_queue) == 1


class TestRows6StoreOutages:
    def test_dedupe_outage_does_not_break_intake(self) -> None:
        """Pipeline contract: dedupe failure degrades, never 500s the member."""
        from gatehouse.runtime import Runtime, run_pipeline

        rt = Runtime(
            settings=Settings(environment="local"),
            bindings=None,  # type: ignore[arg-type]  # not reached below
            dedupe=_DedupeOutage(),
            bundles=None,  # type: ignore[arg-type]
            graph=InMemoryGraphStore(),
            notifier=None,  # type: ignore[arg-type]
            pack=load_pack(PACK),
            model=MockModel(tool_payload={"scam_likelihood": 0.05, "reason_code": "NONE"}),
            case_store=None,
        )
        outcome = go(
            run_pipeline(
                rt,
                channel="telegram",
                household_id="hh-row6",
                sender_name="t",
                text="hello there friend",
                is_forward=False,
            )
        )
        assert outcome.status == "investigated"

    def test_bundle_write_failure_does_not_break_reply(self) -> None:
        from gatehouse.runtime import Runtime, run_pipeline

        class _DeadBundles:
            def write(self, bundle: Any) -> dict[str, Any]:
                raise _Boom("table gone")

            def latest(self, household_id: str, case_id: str) -> None:
                return None

        rt = Runtime(
            settings=Settings(environment="local"),
            bindings=None,  # type: ignore[arg-type]
            dedupe=InMemoryDedupeStore(),
            bundles=_DeadBundles(),
            graph=InMemoryGraphStore(),
            notifier=None,  # type: ignore[arg-type]
            pack=load_pack(PACK),
            model=MockModel(tool_payload={"scam_likelihood": 0.05, "reason_code": "NONE"}),
            case_store=None,
        )
        outcome = go(
            run_pipeline(
                rt,
                channel="telegram",
                household_id="hh-row6b",
                sender_name="t",
                text="another perfectly fine message",
                is_forward=False,
            )
        )
        assert outcome.status == "investigated"
        assert outcome.reply_text


class TestRow7SpendBreakerTrips:
    def test_breaker_refusal_is_visible_not_silent(self) -> None:
        from gatehouse.spend import SpendMeter

        meter = SpendMeter(max_usd=0.0, max_calls=5)  # budget already exhausted
        result = _investigate("urgent KYC, pay now at http://sbi-verify.top", meter=meter)
        assert result.triage_result is not None
        assert result.triage_result.reason_code == "budget_refused"
        assert "TRIAGE_BUDGET_REFUSED" in result.degraded_flags

    def test_breaker_still_produces_verdict(self) -> None:
        from gatehouse.spend import SpendMeter

        meter = SpendMeter(max_usd=0.0, max_calls=5)
        result = _investigate("plain message nothing wrong", meter=meter)
        assert result.verdict in ("SAFE", "NEEDS_HUMAN")


class TestCanaryTripDrill:
    """P4 scope: the canary trip drill, forced in code before staging."""

    def test_clean_reply_passes_through(self) -> None:
        from gatehouse.runtime import apply_canary_guard

        result = _investigate("check http://random-site.example please")
        reply = "✅ Nothing harmful found in this message."
        guarded = apply_canary_guard(result, reply)
        assert "CANARY_TRIP" not in result.reason_codes
        assert guarded == reply

    def test_leaked_canary_replaces_reply_and_flags_critical(self) -> None:
        from gatehouse.runtime import apply_canary_guard

        result = _investigate("check http://random-site.example please")
        leak = f"✅ verified. audit marker: {result.canary}"
        guarded = apply_canary_guard(result, leak)
        assert "CANARY_TRIP" in result.reason_codes
        assert "CANARY_TRIP" in result.degraded_flags
        assert result.canary not in guarded
        assert "verified" not in guarded

    def test_guardian_card_summary_never_carries_canary(self) -> None:
        from gatehouse.channels.notify import LoggingNotifier, NotificationService
        from gatehouse.config import Settings
        from gatehouse.runtime import _escalate

        # Build a real result whose reason codes contain the canary.
        result = _investigate(
            "Your KYC has expired, pay now to scammer99@ybl today urgent",
            model=MockModel(tool_payload={"scam_likelihood": 0.97, "reason_code": "KYC"}),
        )
        result.reason_codes = [f"injected {result.canary}", "PAYMENT_INTENT"]
        sent: list[str] = []

        class _CaptureNotifier(LoggingNotifier):
            def send(self, chat_id: str, text: str) -> bool:
                sent.append(text)
                return True

        svc = NotificationService(_CaptureNotifier())
        s = Settings(environment="local", guardian_telegram_chat_id="123")

        class _RT:
            settings = s
            notification_service_called = False

            def notification_service(self) -> NotificationService:
                self.notification_service_called = True
                return svc

        rt = _RT()
        escalate = _escalate  # imported above; drive it directly
        outcome = escalate(
            rt,  # type: ignore[arg-type]
            result,
            household_id="hh",
            channel="telegram",
            case_id=result.case_id,
            panic=False,
            now=NOON_IST_EPOCH,
        )
        assert outcome == "sent"
        assert sent and all(result.canary not in text for text in sent)
        assert "PAYMENT_INTENT" in sent[0]  # clean codes still delivered


class TestTracesReconstructCase:
    """P4 exit evidence: one trace rebuilds the whole case."""

    def test_trace_spans_cover_every_stage(self) -> None:
        from gatehouse.tracing import CaseTrace

        trace = CaseTrace(case_id="case-t", channel="telegram")
        _investigate(
            "SBI KYC expired, pay now at http://sbi-verify.top",
            model=MockModel(tool_payload={"scam_likelihood": 0.97, "reason_code": "KYC"}),
            trace=trace,
        )
        stages = [span.stage for span in trace.spans]
        assert stages == ["triage", "verify", "graph", "guardian"]
        assert all(span.status == "ok" for span in trace.spans)
        assert trace.notes.get("verdict") in ("SCAM", "SUSPICIOUS")
        assert "spend_usd" in trace.notes

    def test_failed_dependency_marks_span(self) -> None:
        from gatehouse.tracing import CaseTrace

        trace = CaseTrace(case_id="case-t2")
        _investigate("pay to scammer99@ybl immediately", store=_DeadStore(), trace=trace)
        by_stage = {span.stage: span for span in trace.spans}
        assert by_stage["graph"].status == "failed"
        assert by_stage["graph"].error == "_Boom"
        assert by_stage["guardian"].status == "ok"


# Carries a UTR so the graph stage actually queries the store: without an
# identifier the stage short-circuits to the empty finding and a dead store is
# never reached. The extra evidence also lifts confidence past the floor.
_SETTLED_SCAM = "SBI KYC expired, pay now at http://sbi-verify.top UTR123456789012"


class TestRow9SilenceUnderDegradation:
    """Doc 19 section 3 meets charter principle 5: a degraded case is visible.

    Silence is earned. When a dependency did not answer, the confidence on
    the verdict was computed over partial evidence, so handling it silently
    would hide the case and the outage together.
    """

    def test_lost_verification_is_never_silenced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _verify_boom(monkeypatch)
        result = _investigate(
            "SBI KYC expired, pay now at http://sbi-verify.top",
            model=MockModel(tool_payload={"scam_likelihood": 0.99, "reason_code": "KYC"}),
        )
        assert result.package is not None
        assert result.package.silence_band != "SILENT_KILL"

    def test_graph_outage_keeps_a_settled_scam_visible(self) -> None:
        """Hard evidence still convicts, but the outage must reach a human."""
        result = _investigate(
            _SETTLED_SCAM,
            store=_DeadStore(),
            model=MockModel(tool_payload={"scam_likelihood": 0.99, "reason_code": "KYC"}),
        )
        assert "GRAPH_UNAVAILABLE" in result.degraded_flags
        assert result.package is not None
        assert result.package.silence_band != "SILENT_KILL"

    def test_clean_settled_scam_still_earns_silence(self) -> None:
        """The guard must not silence everything: a clean case still goes quiet."""
        result = _investigate(
            _SETTLED_SCAM,
            model=MockModel(tool_payload={"scam_likelihood": 0.99, "reason_code": "KYC"}),
        )
        assert result.degraded_flags == []
        assert result.package is not None
        assert result.package.silence_band == "SILENT_KILL"
