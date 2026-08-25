"""Tests for the in-memory graph store and taint propagation."""

from __future__ import annotations

import pytest

from gatehouse.graph.store import InMemoryGraphStore, finding_unavailable


class TestUpsert:
    def test_new_node_created(self) -> None:
        store = InMemoryGraphStore()
        store.upsert_event(
            [("PHONE", "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6")], taint_base=0.6, case_id="c1"
        )
        found = store.query(["a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"])
        assert len(found) == 1
        assert found[0].event_count == 1
        assert found[0].taint == 0.6

    def test_idempotent_per_case(self) -> None:
        store = InMemoryGraphStore()
        store.upsert_event(
            [("PHONE", "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6")], taint_base=0.6, case_id="c1"
        )
        store.upsert_event(
            [("PHONE", "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6")], taint_base=0.6, case_id="c1"
        )
        assert store.query(["a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"])[0].event_count == 1

    def test_repeat_event_increments(self) -> None:
        store = InMemoryGraphStore()
        store.upsert_event(
            [("PHONE", "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6")], taint_base=0.6, case_id="c1"
        )
        store.upsert_event(
            [("PHONE", "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6")], taint_base=0.6, case_id="c2"
        )
        assert store.query(["a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"])[0].event_count == 2

    def test_taint_takes_max(self) -> None:
        store = InMemoryGraphStore()
        store.upsert_event(
            [("VPA", "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e1")], taint_base=0.6, case_id="c1"
        )
        store.upsert_event(
            [("VPA", "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e1")], taint_base=0.9, case_id="c2"
        )
        store.upsert_event(
            [("VPA", "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e1")], taint_base=0.3, case_id="c3"
        )
        assert store.query(["b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e1"])[0].taint == 0.9


class TestPropagation:
    def test_neighbor_taint_propagates_with_decay(self) -> None:
        store = InMemoryGraphStore()
        # case c1 links phone h1 (confirmed scam 0.9) with VPA h2 (new, clean)
        store.upsert_event(
            [
                ("PHONE", "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"),
                ("VPA", "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e1"),
            ],
            taint_base=0.9,
            case_id="c1",
        )
        # the VPA itself only ever appeared once; its own taint is 0.9 from that
        # case, so instead test a third id linked only via a second case:
        store.upsert_event(
            [
                ("VPA", "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e1f2"),
                ("PHONE", "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"),
            ],
            taint_base=0.0,
            case_id="c2",
        )
        # h3 co-occurred with tainted h1; propagation must lift it above 0
        propagated = store.propagate("c3d4e5f6a7b8c9d0e1f2a3b4c5d6e1f2")
        assert propagated > 0.0
        assert propagated <= 1.0

    def test_no_neighbor_no_lift(self) -> None:
        store = InMemoryGraphStore()
        store.upsert_event(
            [("EMAIL", "d4e5f6a7b8c9d0e1f2a3b4c5d6e1f2a3")], taint_base=0.0, case_id="c1"
        )
        assert store.propagate("d4e5f6a7b8c9d0e1f2a3b4c5d6e1f2a3") == 0.0

    def test_finding_bundles(self) -> None:
        store = InMemoryGraphStore()
        store.upsert_event(
            [
                ("PHONE", "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"),
                ("VPA", "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e1"),
            ],
            taint_base=0.9,
            case_id="c1",
        )
        finding = store.finding_for(
            ["a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6", "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e1"]
        )
        assert finding.prior_events == 2
        assert len(finding.identifiers) == 2
        assert finding.unavailable is False

    def test_unavailable_finding(self) -> None:
        f = finding_unavailable("store down")
        assert f.unavailable is True
        assert f.prior_events == 0


class TestEdgeCases:
    def test_query_unknown_returns_empty(self) -> None:
        store = InMemoryGraphStore()
        assert store.query(["0123456789abcdef0123456789abcdef"]) == []

    def test_propagation_capped_at_one(self) -> None:
        store = InMemoryGraphStore()
        store.upsert_event(
            [("PHONE", "a"), ("VPA", "b"), ("EMAIL", "c")], taint_base=1.0, case_id="c1"
        )
        store.upsert_event(
            [("PHONE", "e5f6a7b8c9d0e1f2a3b4c5d6e1f2a3b4"), ("VPA", "b")],
            taint_base=1.0,
            case_id="c2",
        )
        assert store.propagate("e5f6a7b8c9d0e1f2a3b4c5d6e1f2a3b4") <= 1.0


@pytest.mark.parametrize("hops_decay", [0.6])
def test_decay_constant_is_sentinel_lineage(hops_decay: float) -> None:
    store = InMemoryGraphStore(hop_decay=hops_decay)
    assert store.hop_decay == 0.6  # documented constant (doc 06 section 3)
