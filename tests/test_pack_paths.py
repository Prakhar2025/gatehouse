"""Pack path resolution across deployment layouts.

The Lambda 500 family: the pack lookup assumed one filesystem shape, so a
green suite shipped a runtime that could not find its own country pack under
/var/task. These tests pin every supported layout so path drift fails here,
not in production.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gatehouse.runtime import _default_pack_path, _pack_candidates


class TestPackCandidates:
    def test_repo_layout_resolves_two_levels_up(self) -> None:
        # src/gatehouse/runtime.py -> repo root /packs/in/pack.yaml
        package_dir = Path("/repo/src/gatehouse")
        paths = _pack_candidates(package_dir)
        assert paths[0] == Path("/repo/packs/in/pack.yaml")

    def test_layer_layout_present(self) -> None:
        paths = _pack_candidates(Path("/var/task/gatehouse"))
        assert paths[-1] == Path("/opt/packs/in/pack.yaml")


class TestDefaultPackPath:
    def test_override_wins_over_everything(self, tmp_path: Path, monkeypatch: Any) -> None:
        override = tmp_path / "custom-pack.yaml"
        override.write_text("placeholder", encoding="utf-8")
        monkeypatch.setenv("GATEHOUSE_PACK_PATH", str(override))
        assert _default_pack_path() == override

    def test_first_existing_candidate_is_chosen(self, tmp_path: Path, monkeypatch: Any) -> None:
        monkeypatch.delenv("GATEHOUSE_PACK_PATH", raising=False)
        fake_pkg = tmp_path / "task" / "gatehouse"
        fake_pkg.mkdir(parents=True)
        packs = tmp_path / "task" / "packs" / "in"
        packs.mkdir(parents=True)
        (packs / "pack.yaml").write_text("placeholder", encoding="utf-8")

        import gatehouse.runtime as rt

        original = rt._pack_candidates

        def staged_candidates(package_dir: Path) -> list[Path]:
            return [
                tmp_path / "nowhere" / "pack.yaml",
                packs / "pack.yaml",
            ]

        monkeypatch.setattr(rt, "_pack_candidates", staged_candidates)
        try:
            assert _default_pack_path() == packs / "pack.yaml"
        finally:
            rt._pack_candidates = original

    def test_missing_everywhere_returns_repo_candidate_for_clean_error(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        monkeypatch.delenv("GATEHOUSE_PACK_PATH", raising=False)
        import gatehouse.runtime as rt

        def missing_candidates(package_dir: Path) -> list[Path]:
            return [tmp_path / "absent" / "pack.yaml"]

        original = rt._pack_candidates
        monkeypatch.setattr(rt, "_pack_candidates", missing_candidates)
        result = _default_pack_path()
        monkeypatch.setattr(rt, "_pack_candidates", original)
        assert result == tmp_path / "absent" / "pack.yaml"

    def test_real_repo_pack_found_from_installed_location(self, monkeypatch: Any) -> None:
        # The suite itself runs from src/: resolution must land on the real
        # India pack without any env override.
        monkeypatch.delenv("GATEHOUSE_PACK_PATH", raising=False)
        path = _default_pack_path()
        assert path.is_file(), f"pack not resolved from source layout: {path}"
