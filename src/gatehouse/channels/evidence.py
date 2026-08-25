"""Evidence bundle: the durable, human-auditable record of one case (doc 04).

The case store already persists the verdict atomically. The evidence bundle is
the larger artifact the console renders and the audit team reviews. It carries
the canary, the fencing summary, the reason codes, top evidence, graph state
at decision time, and the channel that delivered the signal.

Design rule: the bundle is APPEND-ONLY. Updates to a case produce a new bundle
item with an incremented `revision` field; the original is never overwritten.
This is the rule audit teams rely on (doc 16 risk R-AUD-1).
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from gatehouse.agents.schemas import (
    GraphFinding,
    GuardianPackage,
    TriageResult,
    VerificationFinding,
)
from gatehouse.orchestrator import CaseResult


@dataclass(frozen=True)
class EvidenceBundle:
    """The full artifact the console and audit consume."""

    case_id: str
    household_id: str
    channel: str
    revision: int
    created_at: float
    triage: TriageResult
    verify_findings: tuple[VerificationFinding, ...]
    graph: GraphFinding
    package: GuardianPackage
    spend_usd: float
    canary: str
    raw_text_redacted: str
    reason_codes: tuple[str, ...]
    top_evidence: tuple[str, ...]
    degraded_flags: tuple[str, ...]
    verdict: str
    verdict_confidence: float


def build_bundle(
    case_result: CaseResult,
    triage: TriageResult,
    verify_findings: tuple[VerificationFinding, ...] | list[VerificationFinding],
    graph: GraphFinding,
    package: GuardianPackage,
    household_id: str,
    channel: str,
    raw_text_redacted: str,
    now: float | None = None,
) -> EvidenceBundle:
    """Build the bundle from the in-memory orchestrator outputs."""
    return EvidenceBundle(
        case_id=case_result.case_id,
        household_id=household_id,
        channel=channel,
        revision=1,
        created_at=now if now is not None else time.time(),
        triage=triage,
        verify_findings=tuple(verify_findings),
        graph=graph,
        package=package,
        spend_usd=case_result.spend_usd,
        canary=case_result.canary,
        raw_text_redacted=raw_text_redacted,
        reason_codes=tuple(package.reason_codes),
        top_evidence=tuple(package.top_evidence),
        degraded_flags=tuple(package.degraded_flags),
        verdict=package.verdict,
        verdict_confidence=package.confidence,
    )


def new_case_id() -> str:
    """Short, URL-safe case id; collision probability is irrelevant at v1 scale."""
    return uuid.uuid4().hex[:16]


class BundleStore(Protocol):
    """Persistence of the bundle, separate from the atomic verdict write."""

    def write(self, bundle: EvidenceBundle) -> dict[str, Any]: ...
    def latest(self, household_id: str, case_id: str) -> EvidenceBundle | None: ...


class InMemoryBundleStore:
    """Process-local; unit tests, dev, and the Journey A harness."""

    def __init__(self) -> None:
        # key: (household, case_id) -> EvidenceBundle (latest revision only)
        self._latest: dict[tuple[str, str], EvidenceBundle] = {}

    def write(self, bundle: EvidenceBundle) -> dict[str, Any]:
        self._latest[(bundle.household_id, bundle.case_id)] = bundle
        return {"written": True, "case_id": bundle.case_id, "revision": bundle.revision}

    def latest(self, household_id: str, case_id: str) -> EvidenceBundle | None:
        return self._latest.get((household_id, case_id))


class DynamoBundleStore:
    """DynamoDB bundle persistence. Key pattern BUNDLE#<household>#<case_id> with
    SK BUNDLE#<revision> so multiple revisions can coexist; queries use the
    well-known partition + sort key prefix."""

    def __init__(self, client: Any, table_name: str) -> None:
        self._client = client
        self._table = table_name

    def write(self, bundle: EvidenceBundle) -> dict[str, Any]:
        self._client.put_item(
            TableName=self._table,
            Item={
                "pk": {"S": f"HOUSEHOLD#{bundle.household_id}"},
                "sk": {"S": f"CASE#{bundle.case_id}#BUNDLE#{bundle.revision:04d}"},
                "case_id": {"S": bundle.case_id},
                "channel": {"S": bundle.channel},
                "verdict": {"S": bundle.verdict},
                "verdict_confidence": {"N": str(bundle.verdict_confidence)},
                "canary": {"S": bundle.canary},
                "spend_usd": {"N": str(bundle.spend_usd)},
                "reason_codes": {"SS": list(bundle.reason_codes) or ["NONE"]},
                "top_evidence": {"SS": list(bundle.top_evidence) or ["NONE"]},
                "degraded_flags": {"SS": list(bundle.degraded_flags) or ["NONE"]},
                "raw_text_redacted": {"S": bundle.raw_text_redacted},
                "triage": {"S": bundle.triage.model_dump_json()},
                "verify_findings": {
                    "S": json.dumps([f.model_dump() for f in bundle.verify_findings])
                },
                "graph": {"S": bundle.graph.model_dump_json()},
                "package": {"S": bundle.package.model_dump_json()},
                "created_at": {"N": str(int(bundle.created_at))},
            },
        )
        return {"written": True, "case_id": bundle.case_id, "revision": bundle.revision}

    def latest(self, household_id: str, case_id: str) -> EvidenceBundle | None:
        # Production: would use Query with ScanIndexForward=False and Limit=1
        # against BUNDLE#* SK; left as the deploy layer's responsibility.
        return None
