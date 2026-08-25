"""Threat graph store: hashed nodes, weighted adjacency, taint (doc 06 section 3).

P2 ships the in-memory store behind the GraphStore protocol; the DynamoDB
implementation arrives with P4 deployment behind the same interface. Taint math
is deterministic and unit-tested: base by verdict source, 0.6^hops decay
(Sentinel lineage), exponential time decay with 45-day half-life-ish constant.
"""

from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Protocol

from gatehouse.agents.schemas import GraphFinding, GraphIdentifier


class GraphStore(Protocol):
    """Storage-agnostic graph contract."""

    def upsert_event(
        self,
        identifiers: list[tuple[str, str]],  # (kind, hashed_value)
        taint_base: float,
        case_id: str,
        now: float | None = None,
    ) -> None: ...

    def query(self, hashed_values: list[str]) -> list[GraphIdentifier]: ...

    def finding_for(self, hashed_values: list[str], now: float | None = None) -> GraphFinding: ...


@dataclass
class _Node:
    kind: str
    hashed: str
    first_seen: float
    last_seen: float
    event_count: int = 0
    taint: float = 0.0


@dataclass
class InMemoryGraphStore:
    """Deterministic in-memory implementation; swapped for DynamoDB in P4."""

    hop_decay: float = 0.6
    time_decay_days: float = 45.0
    _nodes: dict[str, _Node] = field(default_factory=dict)
    # co-occurrence edges: hashed -> {hashed -> weight}
    _edges: dict[str, dict[str, float]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(float))
    )

    # -- GraphStore ---------------------------------------------------------
    def upsert_event(
        self,
        identifiers: list[tuple[str, str]],
        taint_base: float,
        case_id: str,
        now: float | None = None,
    ) -> None:
        """Record one case's identifiers; co-occurring ids gain mutual weight.

        Idempotent per case: (case_id) seen before is a no-op, matching the
        orchestrator's retry-safe graph commit contract.
        """
        ts = time.time() if now is None else now
        if not hasattr(self, "_seen_cases"):
            self._seen_cases: set[str] = set()
        if case_id in self._seen_cases:
            return
        self._seen_cases.add(case_id)

        nodes: list[_Node] = []
        for kind, hashed in identifiers:
            key = f"{kind}:{hashed}"
            node = self._nodes.get(key)
            if node is None:
                node = _Node(kind=kind, hashed=hashed, first_seen=ts, last_seen=ts)
                self._nodes[key] = node
            node.last_seen = ts
            node.event_count += 1
            node.taint = max(node.taint, taint_base)
            nodes.append(node)

        # pairwise co-occurrence edges (small cliques: <= ~5 ids per case)
        for i, a in enumerate(nodes):
            for b in nodes[i + 1 :]:
                key_a, key_b = f"{a.kind}:{a.hashed}", f"{b.kind}:{b.hashed}"
                self._edges[key_a][key_b] += 1.0
                self._edges[key_b][key_a] += 1.0

    def query(self, hashed_values: list[str]) -> list[GraphIdentifier]:
        """Return current knowledge for the given hashed ids."""
        results: list[GraphIdentifier] = []
        for hashed in hashed_values:
            for kind in ("PHONE", "VPA", "DOMAIN", "URL_PATH", "BANK_ACCT", "EMAIL", "UTR_REF"):
                key = f"{kind}:{hashed}"
                node = self._nodes.get(key)
                if node is not None:
                    results.append(
                        GraphIdentifier(
                            kind=kind,
                            hashed_value=node.hashed,
                            first_seen=str(node.first_seen),
                            last_seen=str(node.last_seen),
                            event_count=node.event_count,
                            taint=round(node.taint, 4),
                            coverage_note="in-memory store",
                        )
                    )
                    break
        return results

    # -- taint internals -----------------------------------------------------
    def propagate(self, seed_hashed: str, now: float | None = None) -> float:
        """One-hop taint propagation from a seed through co-occurrence edges."""
        ts = time.time() if now is None else now
        best = 0.0
        for key, node in self._nodes.items():
            if not key.endswith(f":{seed_hashed}"):
                continue
            total = node.taint
            for neighbor_key, weight in self._edges.get(key, {}).items():
                neighbor = self._nodes.get(neighbor_key)
                if neighbor is None:
                    continue
                days = max(0.0, (ts - neighbor.last_seen) / 86400.0)
                time_factor = math.exp(-days / self.time_decay_days)
                total = max(
                    total,
                    neighbor.taint * (self.hop_decay**1) * time_factor * min(weight, 3.0) / 3.0,
                )
            best = max(best, min(total, 1.0))
        return round(best, 4)

    def finding_for(self, hashed_values: list[str], now: float | None = None) -> GraphFinding:
        """Bundle a query + best propagation into a GraphFinding."""
        ts = time.time() if now is None else now
        ids = self.query(hashed_values)
        prior = sum(i.event_count for i in ids)
        max_taint = max((self.propagate(i.hashed_value, ts) for i in ids), default=0.0)
        return GraphFinding(
            identifiers=ids,
            prior_events=prior,
            max_taint=max_taint,
            unavailable=False,
        )


def finding_unavailable(reason: str) -> GraphFinding:
    """Honest degraded finding when the store cannot be reached."""
    return GraphFinding(
        identifiers=[],
        prior_events=0,
        max_taint=0.0,
        unavailable=True,
    )
