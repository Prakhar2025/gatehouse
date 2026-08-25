"""Tests for the signed event envelope (doc 05 section 5)."""

from __future__ import annotations

from gatehouse.channels.events import (
    GatewayEvent,
    build_envelope,
    content_hash,
    event_id,
    sign_event,
    verify_event,
)


def _event(**overrides: object) -> GatewayEvent:
    base: dict[str, object] = {
        "channel": "telegram",
        "household_id": "fam-1",
        "sender_name": "T",
        "text": "urgent kyc update",
        "is_forward": True,
        "received_at": 1000.0,
    }
    base.update(overrides)
    return GatewayEvent(**base)  # type: ignore[arg-type]


class TestEventId:
    def test_identity_is_channel_hash_household(self) -> None:
        e = _event()
        assert event_id(e).startswith("telegram#")
        assert event_id(e).endswith("#fam-1")

    def test_same_content_same_id(self) -> None:
        assert event_id(_event()) == event_id(_event())

    def test_different_household_different_id(self) -> None:
        assert event_id(_event()) != event_id(_event(household_id="fam-2"))

    def test_text_cap_enforced(self) -> None:
        envelope = build_envelope(_event(text="a" * 9000))
        assert len(envelope["text"]) == 4000


class TestEnvelopeSignature:
    def test_sign_and_verify_roundtrip(self) -> None:
        env = build_envelope(_event())
        sig = sign_event(env, "k")
        assert verify_event(env, sig, "k") is True

    def test_tampered_body_fails(self) -> None:
        env = build_envelope(_event())
        sig = sign_event(env, "k")
        tampered = dict(env)
        tampered["text"] = "changed"
        assert verify_event(tampered, sig, "k") is False

    def test_wrong_key_fails(self) -> None:
        env = build_envelope(_event())
        sig = sign_event(env, "k1")
        assert verify_event(env, sig, "k2") is False

    def test_missing_signature_fails(self) -> None:
        assert verify_event(build_envelope(_event()), None, "k") is False

    def test_deterministic_across_key_order(self) -> None:
        env_a = build_envelope(_event())
        env_b = dict(reversed(list(env_a.items())))
        assert sign_event(env_a, "k") == sign_event(env_b, "k")


class TestContentHashParity:
    def test_matches_dedupe_layer_hash(self) -> None:
        from gatehouse.channels.dedupe import content_hash as dedupe_hash

        assert content_hash(" hello ") == dedupe_hash(" hello ")
