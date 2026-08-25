"""Tests for pack schemas, loader, and the India v0 artifact."""

from __future__ import annotations

from pathlib import Path

import pytest

from gatehouse.packs.loader import PackError, compute_checksum, load_pack, validate_pack_dir
from gatehouse.packs.schemas import CountryPack

REPO = Path(__file__).resolve().parents[2]
INDIA_PACK = REPO / "packs" / "in" / "pack.yaml"


@pytest.fixture(scope="module")
def india() -> CountryPack:
    return load_pack(INDIA_PACK)


class TestLoader:
    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(PackError, match="not found"):
            load_pack(tmp_path / "nope.yaml")

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("a: [unclosed", encoding="utf-8")
        with pytest.raises(PackError, match="invalid YAML"):
            load_pack(bad)

    def test_non_mapping_root_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "list.yaml"
        bad.write_text("- just\n- a list\n", encoding="utf-8")
        with pytest.raises(PackError, match="mapping"):
            load_pack(bad)

    def test_schema_violation_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "schema.yaml"
        bad.write_text("region: inzz\nversion: 0.1.0\n", encoding="utf-8")
        with pytest.raises(PackError, match="schema violation"):
            load_pack(bad)

    def test_unknown_fields_rejected(self) -> None:
        raw: dict[str, object] = {
            "region": "in",
            "version": "0.1.0",
            "languages": ["en"],
            "lexicons": [{"lang": "en", "strong": ["x"]}],
            "scoring": {
                "strong_phrase": 0.4,
                "moderate_phrase": 0.3,
                "weak_phrase": 0.1,
                "payment_intent_bonus": 0.2,
                "url_present_bonus": 0.1,
            },
            "sneaky_extra": True,
        }
        with pytest.raises(PackError, match="schema violation"):
            load_pack_path_helper(raw)


def load_pack_path_helper(raw: dict[str, object]) -> CountryPack:
    import tempfile

    from gatehouse.packs.loader import load_pack as lp

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fh:
        import yaml

        yaml.safe_dump(raw, fh)
        path = Path(fh.name)
    return lp(path)


class TestIndiaPack:
    def test_loads(self, india: CountryPack) -> None:
        assert india.region == "in"
        assert india.version == "0.1.0"

    def test_languages(self, india: CountryPack) -> None:
        assert "en" in india.languages and "hi" in india.languages

    def test_has_issuers_and_rails(self, india: CountryPack) -> None:
        assert len(india.issuers) >= 5
        assert any(rail.id == "upi" for rail in india.rails)

    def test_domain_helpers(self, india: CountryPack) -> None:
        domains = india.issuer_domains()
        assert "sbi.co.in" in domains
        senders = india.issuer_sms_senders()
        assert "sbibnk" in senders  # lowercased

    def test_validate_dir_all_ok(self) -> None:
        results = validate_pack_dir(REPO / "packs")
        assert results
        assert all(status.startswith("OK") for _, status in results)

    def test_checksum_stable(self) -> None:
        assert compute_checksum(INDIA_PACK) == compute_checksum(INDIA_PACK)
