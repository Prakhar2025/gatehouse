"""Live runtime wiring: binds stores, model, notifier, and pipeline together.

This module is the deployment-layer composition root (doc 09 section 2). The
intake API and the Lambda handler both delegate here instead of running a
placeholder verdict. Backend selection follows the environment:

- local:      in-memory stores, logging notifier, no external model. The full
              loop runs offline, which is what unit tests and dev servers use.
- staging/prod: DynamoDB-backed stores, real Telegram sender, Bedrock model.

Every builder is injectable so tests can substitute fakes without network.
The pipeline itself is transport-agnostic: Telegram and email handlers reduce
their payloads to (channel, household, sender, text) and call the same code.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gatehouse.channels.binding import (
    AlreadyLinkedError,
    BindingStore,
    DynamoBindingStore,
    InMemoryBindingStore,
    InviteError,
    UnlinkedSenderError,
    verify_sender,
)
from gatehouse.channels.dedupe import DedupeStore, DynamoDedupeStore, InMemoryDedupeStore
from gatehouse.channels.events import GatewayEvent, build_envelope
from gatehouse.channels.evidence import (
    BundleStore,
    DynamoBundleStore,
    InMemoryBundleStore,
    new_case_id,
)
from gatehouse.channels.notify import (
    EscalationCard,
    LoggingNotifier,
    NotificationError,
    NotificationService,
    Notifier,
)
from gatehouse.channels.telegram import build_reply_verdict
from gatehouse.config import Settings, get_settings
from gatehouse.graph.store import GraphStore
from gatehouse.logging_utils import get_logger, scrub_p1
from gatehouse.orchestrator import CaseResult, investigate
from gatehouse.packs.loader import load_pack
from gatehouse.packs.schemas import CountryPack
from gatehouse.persistence import CaseStore
from gatehouse.spend import SpendMeter

log = get_logger("gatehouse.runtime")

_VERDICT_TO_URGENCY = {"SCAM": "EMERGENCY", "SUSPICIOUS": "DECISION"}


class PipelineOutcome:
    """What one inbound signal produced, for the HTTP response and logs."""

    __slots__ = (
        "case_id",
        "escalated",
        "household_id",
        "latency_s",
        "reason_codes",
        "reply_text",
        "spend_usd",
        "status",
        "verdict",
    )

    def __init__(
        self,
        status: str,
        reply_text: str,
        case_id: str | None = None,
        verdict: str | None = None,
        reason_codes: list[str] | None = None,
        household_id: str | None = None,
        latency_s: float = 0.0,
        escalated: str | None = None,
        spend_usd: float = 0.0,
    ) -> None:
        self.status = status
        self.reply_text = reply_text
        self.case_id = case_id
        self.verdict = verdict
        self.reason_codes = reason_codes or []
        self.household_id = household_id
        self.latency_s = latency_s
        self.escalated = escalated
        self.spend_usd = spend_usd


@dataclass
class Runtime:
    """One composed set of collaborators for the loop."""

    settings: Settings
    bindings: BindingStore
    dedupe: DedupeStore
    bundles: BundleStore
    graph: GraphStore
    notifier: Notifier
    pack: CountryPack
    model: Any | None = None
    case_store: CaseStore | None = None
    bus_publisher: Any | None = None
    bus_name: str = ""
    notifications: NotificationService | None = None

    def notification_service(self) -> NotificationService:
        """Lazy service so the digest queue survives per process, not per call."""
        if self.notifications is None:
            self.notifications = NotificationService(self.notifier)
        return self.notifications


_RUNTIME: Runtime | None = None


def reset_runtime() -> None:
    """Test hook: drop the cached composition so factories re-run."""
    global _RUNTIME
    _RUNTIME = None


def _default_pack_path() -> Path:
    """Pack location: override via GATEHOUSE_PACK_PATH (Lambda layer /opt),
    else the repo layout for local dev and tests."""
    override = os.environ.get("GATEHOUSE_PACK_PATH")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "packs" / "in" / "pack.yaml"


_PACK_CACHE: dict[str, CountryPack] = {}


def load_pack_cached(path: Path | None = None) -> CountryPack:
    """Load the India pack once per process."""
    p = path or _default_pack_path()
    key = str(p)
    if key not in _PACK_CACHE:
        _PACK_CACHE[key] = load_pack(p)
    return _PACK_CACHE[key]


# --- backend builders -------------------------------------------------------


def _aws_client(service: str) -> Any:
    """Lazy boto3 client factory; tests monkeypatch this to stay offline."""
    import boto3

    # Any-aliased because the SDK stubs demand literal service names.
    client_factory: Any = boto3.client
    return client_factory(service)


def build_bindings(settings: Settings) -> BindingStore:
    if settings.environment == "local":
        return InMemoryBindingStore()
    return DynamoBindingStore(_aws_client("dynamodb"), settings.cases_table_name)


def build_dedupe(settings: Settings) -> DedupeStore:
    ttl = {
        "telegram": settings.dedupe_ttl_hours * 3600,
        "whatsapp": settings.dedupe_ttl_hours * 3600,
        "email": 7 * 24 * 3600,
        "api": 24 * 3600,
    }
    if settings.environment == "local":
        return InMemoryDedupeStore(ttl_seconds_by_channel=ttl)
    return DynamoDedupeStore(
        _aws_client("dynamodb"), settings.cases_table_name, ttl_seconds_by_channel=ttl
    )


def build_bundles(settings: Settings) -> BundleStore:
    if settings.environment == "local":
        return InMemoryBundleStore()
    return DynamoBundleStore(_aws_client("dynamodb"), settings.cases_table_name)


def build_graph(settings: Settings) -> GraphStore:
    if settings.environment == "local":
        from gatehouse.graph.store import InMemoryGraphStore

        return InMemoryGraphStore()
    from gatehouse.runtime_dynamo import DynamoGraphStore

    return DynamoGraphStore(_aws_client("dynamodb"), settings.graph_table_name)


def build_notifier(settings: Settings) -> Notifier:
    if settings.environment == "local" or not settings.telegram_bot_token:
        return LoggingNotifier()
    from gatehouse.runtime_telegram import TelegramSender

    return TelegramSender(settings.telegram_bot_token)


def build_model(settings: Settings) -> Any | None:
    """None means the orchestrator degrades to rules-only, honestly flagged."""
    if settings.environment == "local":
        return None
    from strands.models import BedrockModel

    return BedrockModel(model_id=settings.bedrock_model_id, region_name=settings.region)


def build_case_store(settings: Settings) -> CaseStore | None:
    if settings.environment == "local":
        return None  # local loop skips Dynamo verdict writes; bundles suffice
    return CaseStore(_aws_client("dynamodb"), settings.cases_table_name, settings)


def build_bus_publisher(settings: Settings) -> Any | None:
    if settings.environment == "local":
        return None
    from gatehouse.channels.bus import EventBridgePublisher

    return EventBridgePublisher(_aws_client("events"), settings.graph_salt)


def get_runtime(settings: Settings | None = None) -> Runtime:
    """Composed-once accessor; Lambda warm containers reuse everything."""
    global _RUNTIME
    if _RUNTIME is None:
        s = settings or get_settings()
        _RUNTIME = Runtime(
            settings=s,
            bindings=build_bindings(s),
            dedupe=build_dedupe(s),
            bundles=build_bundles(s),
            graph=build_graph(s),
            notifier=build_notifier(s),
            pack=load_pack_cached(),
            model=build_model(s),
            case_store=build_case_store(s),
            bus_publisher=build_bus_publisher(s),
            bus_name=s.event_bus_name,
        )
        log.info(
            "runtime_composed",
            extra={
                "extra_fields": {
                    "environment": s.environment,
                    "model": s.bedrock_model_id if s.environment != "local" else "rules_only",
                }
            },
        )
    return _RUNTIME


# --- the pipeline -----------------------------------------------------------


async def run_pipeline(
    rt: Runtime,
    *,
    channel: str,
    household_id: str,
    sender_name: str,
    text: str,
    is_forward: bool,
    meter: SpendMeter | None = None,
    now: float | None = None,
    has_media: bool = False,
) -> PipelineOutcome:
    """Full live loop for one accepted, bound signal."""
    started = time.perf_counter()

    # 1) panic short-circuits dedupe and quiet hours downstream.
    from gatehouse.channels.telegram import is_panic_request

    panic = is_panic_request(text)
    if panic:
        text = text.strip()[6:].strip() or text.strip()

    # 2) duplicate-forward budget protection (doc 05 section 5). One
    # conditional call reserves the slot under the real case id.
    # A screenshot with no text layer has no content hash yet; skipping the
    # short-circuit keeps two different screenshots from colliding as
    # duplicates. Content-based hashing returns with the OCR normalize stage.
    media_only = has_media and not text.strip()
    case_id = new_case_id()
    hit = (
        None
        if media_only
        else rt.dedupe.check_and_record(channel, household_id, text, case_id, now=now)
    )
    if hit is not None:
        return PipelineOutcome(
            status="duplicate",
            reply_text=(
                f"Already checked this one: case {hit.case_id}. No new investigation was run."
            ),
            case_id=hit.case_id,
            household_id=household_id,
            latency_s=time.perf_counter() - started,
        )

    # 3) publish the signed envelope onto the bus (observability arm).
    if rt.bus_publisher is not None:
        try:
            envelope = build_envelope(
                GatewayEvent(
                    channel=channel,
                    household_id=household_id,
                    sender_name=sender_name,
                    text=text,
                    is_forward=is_forward,
                    received_at=time.time(),
                )
            )
            envelope["event_bus_name"] = rt.bus_name
            pub = rt.bus_publisher.publish([envelope])
            if pub.failed:
                log.warning("bus_publish_partial", extra={"extra_fields": {"failed": pub.failed}})
        except Exception as exc:
            log.warning("bus_publish_failed", extra={"extra_fields": {"error": type(exc).__name__}})

    # 3.5) a screenshot with no text layer still gets a completed, honest
    # investigation (doc 05 section 7). The placeholder is deterministic and
    # clearly marked; the real OCR path replaces it in the normalize stage
    # without changing this contract.
    media_flags: list[str] = []
    if has_media and not text.strip():
        text = "[media: image, no extractable text]"
        media_flags = ["NO_TEXT_LAYER"]

    # 4) investigate (fence -> triage -> verify -> graph -> guardian).
    result: CaseResult = await investigate(
        case_id,
        text,
        rt.pack,
        rt.graph,
        settings=rt.settings,
        model=rt.model,
        meter=meter,
    )
    if media_flags:
        result.reason_codes = list(result.reason_codes) + media_flags

    # 5) persist evidence bundle (+ atomic verdict write when backed).
    _write_bundle(rt, result, household_id, channel, text)
    if rt.case_store is not None and result.package is not None:
        try:
            rt.case_store.save_verdict(
                household_id, case_id, result.package, result.triage_class, result.spend_usd
            )
        except Exception as exc:
            log.warning("case_write_failed", extra={"extra_fields": {"error": type(exc).__name__}})

    # 6) guardian escalation (SCAM bypasses quiet hours as EMERGENCY).
    escalated = _escalate(rt, result, household_id, channel, case_id, panic, now=now)

    reply = build_reply_verdict(result.verdict, result.reason_codes)
    return PipelineOutcome(
        status="investigated",
        reply_text=reply,
        case_id=case_id,
        verdict=result.verdict,
        reason_codes=result.reason_codes,
        household_id=household_id,
        latency_s=time.perf_counter() - started,
        escalated=escalated,
        spend_usd=result.spend_usd,
    )


def _write_bundle(
    rt: Runtime, result: CaseResult, household_id: str, channel: str, text: str
) -> Any:
    """Build and persist the evidence bundle; never let it break the reply."""
    try:
        from gatehouse.channels.evidence import build_bundle

        if (
            result.triage_result is None
            or result.verify_findings is None
            or result.graph_finding is None
            or result.package is None
        ):
            return None
        bundle = build_bundle(
            result,
            result.triage_result,
            result.verify_findings,
            result.graph_finding,
            result.package,
            household_id=household_id,
            channel=channel,
            raw_text_redacted=scrub_p1(text[:400]),
        )
        rt.bundles.write(bundle)
    except Exception as exc:
        log.warning("bundle_write_failed", extra={"extra_fields": {"error": type(exc).__name__}})
    else:
        return bundle
    return None


def _escalate(
    rt: Runtime,
    result: CaseResult,
    household_id: str,
    channel: str,
    case_id: str,
    panic: bool,
    now: float | None = None,
) -> str | None:
    """Send the guardian card when the package demands action. Best effort."""
    if result.package is None or result.recommended_action == "none":
        return None
    urgency = _VERDICT_TO_URGENCY.get(result.verdict)
    if urgency is None:
        return None
    if panic:
        urgency = "EMERGENCY"
    summary = "; ".join(result.reason_codes[:3]) or "see evidence bundle"
    title = f"{result.verdict} on a {channel} forward"
    card = EscalationCard(
        household_id=household_id,
        case_id=case_id,
        urgency=urgency,
        title=title,
        summary=summary,
    )
    try:
        return rt.notification_service().escalate(card, rt.settings, now=now)
    except NotificationError as exc:
        log.warning("escalation_failed", extra={"extra_fields": {"reason": str(exc)}})
        return None


# --- channel entrypoints ----------------------------------------------------


def _send_member_reply(settings: Settings, chat_id: str, text: str) -> None:
    """Deliver the member-facing reply through Telegram, best effort.

    Webhook HTTP bodies are discarded by Telegram, so the verdict reaches the
    member only via sendMessage. Gated on a configured token and a non-local
    environment: local runs and tests stay fully offline, and a failed send
    logs a warning instead of failing the webhook (the case still exists).
    """
    if settings.environment == "local" or not settings.telegram_bot_token:
        return
    try:
        from gatehouse.runtime_telegram import TelegramSender

        ok = TelegramSender(settings.telegram_bot_token).send(chat_id, text)
        if not ok:
            log.warning("member_reply_send_failed", extra={"extra_fields": {"chat_id": chat_id}})
    except Exception as exc:
        log.warning("member_reply_error", extra={"extra_fields": {"error": type(exc).__name__}})


async def handle_telegram_signal(signal: Any, settings: Settings | None = None) -> PipelineOutcome:
    """Telegram update -> binding check -> live loop. Refusal never spends."""
    rt = get_runtime(settings)
    started = time.perf_counter()

    # 0) /start CODE binds the chat to a household (doc 05 section 2).
    # Handled before the linked-chat check because binding is the one thing
    # an unlinked chat must be able to do. Never spends, never investigates.
    from gatehouse.channels.telegram import parse_start_command

    start = parse_start_command(signal.text)
    if start is not None:
        try:
            binding = rt.bindings.consume_invite(start, "telegram", str(signal.chat_id))
        except InviteError:
            reply = (
                "That invite code is invalid or expired. Ask your family guardian for a fresh code."
            )
            _send_member_reply(rt.settings, str(signal.chat_id), reply)
            return PipelineOutcome(
                status="refused",
                reply_text=reply,
                latency_s=time.perf_counter() - started,
            )
        except AlreadyLinkedError:
            reply = (
                "This chat is already linked to a Gatehouse household. "
                "Forward something anytime and it gets checked."
            )
            _send_member_reply(rt.settings, str(signal.chat_id), reply)
            return PipelineOutcome(
                status="refused",
                reply_text=reply,
                latency_s=time.perf_counter() - started,
            )
        bound_reply = (
            f"Linked. This chat now belongs to {binding.household_id}. "
            "Forward any message that feels risky and Gatehouse checks it."
        )
        _send_member_reply(rt.settings, str(signal.chat_id), bound_reply)
        return PipelineOutcome(
            status="bound",
            reply_text=bound_reply,
            case_id=None,
            household_id=binding.household_id,
            latency_s=time.perf_counter() - started,
        )

    try:
        # Type comes from the consume_invite call above; same Binding shape.
        binding = verify_sender(rt.bindings, "telegram", str(signal.chat_id))
    except UnlinkedSenderError:
        refusal = (
            "This chat is not linked to a Gatehouse household. "
            "Ask your family guardian for an invite code."
        )
        _send_member_reply(rt.settings, str(signal.chat_id), refusal)
        return PipelineOutcome(
            status="refused",
            reply_text=refusal,
            latency_s=time.perf_counter() - started,
        )
    outcome = await run_pipeline(
        rt,
        channel="telegram",
        household_id=binding.household_id,
        sender_name=signal.sender_name,
        text=signal.text,
        is_forward=signal.is_forward,
        has_media=signal.has_media,
    )
    _send_member_reply(rt.settings, str(signal.chat_id), outcome.reply_text)
    return outcome


async def handle_email_signal(
    *, alias: str, sender: str, text: str, message_id: str, settings: Settings | None = None
) -> PipelineOutcome:
    """SES receipt event -> alias allowlist acts as the binding boundary."""
    rt = get_runtime(settings)
    allowed = {a.strip().lower() for a in rt.settings.email_alias_allowlist.split(",") if a.strip()}
    if alias.lower() not in allowed:
        return PipelineOutcome(status="refused", reply_text="")
    return await run_pipeline(
        rt,
        channel="email",
        household_id=f"alias:{alias.lower()}",
        sender_name=sender[:40],
        text=text,
        is_forward=False,
    )


def digest_tick() -> int:
    """Scheduled entry: flush anything parked by quiet hours. Returns count."""
    rt = get_runtime()
    try:
        return rt.notification_service().flush_digest(rt.settings)
    except NotificationError as exc:
        log.warning("digest_flush_failed", extra={"extra_fields": {"reason": str(exc)}})
        return 0


def run_async(coro: Any) -> Any:
    """Sync bridge for the Lambda entrypoint."""
    return asyncio.run(coro)
