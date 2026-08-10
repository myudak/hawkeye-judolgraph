"""Source-tree and installed-wheel resource location tests."""

from __future__ import annotations

from pathlib import Path

import pytest

import hawkeye.paths as path_helpers


def test_controlled_fixture_is_found_beside_an_overlay_wheel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    archive_root = tmp_path / "wheel-archive"
    installed_module = archive_root / "Lib/site-packages/hawkeye/paths.py"
    installed_module.parent.mkdir(parents=True)
    installed_module.write_text("# installation marker\n", encoding="utf-8")
    installed_fixture = archive_root / "share/hawkeye/evaluation/controlled-interactions-v1.json"
    installed_fixture.parent.mkdir(parents=True)
    installed_fixture.write_text('{"scenarios": []}\n', encoding="utf-8")

    monkeypatch.setattr(path_helpers, "__file__", str(installed_module))
    monkeypatch.setattr(path_helpers, "repository_root", lambda start=None: None)
    monkeypatch.setattr(
        path_helpers.sysconfig,
        "get_path",
        lambda name: str(tmp_path / "unrelated-prefix"),
    )

    assert path_helpers.controlled_fixture_path() == installed_fixture
