"""Deterministic offline Gemastik walkthrough coverage using real case and comparison schemas."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from hawkeye.demo import build_demo
from hawkeye.review_app.loader import CaseLoader, case_details


def test_demo_builder_writes_verified_cases_comparison_and_noncanonical_diagnostic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fail_network(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("the offline demo builder must not resolve network hosts")

    monkeypatch.setattr(socket, "getaddrinfo", fail_network)
    result = build_demo(tmp_path / "demo")

    assert result.case_ids == ["demo-harbor", "demo-restricted", "demo-tide"]
    assert result.comparison_path.is_file()
    loader = CaseLoader(result.cases_directory, comparisons_root=result.comparisons_directory)
    summaries = loader.list_cases()
    assert [summary["case_id"] for summary in summaries] == result.case_ids
    assert all(summary["integrity"] == "verified" for summary in summaries)

    harbor = loader.load("demo-harbor")
    comparisons, comparison_warning = loader.comparisons_for_case(harbor)
    payload = case_details(
        harbor,
        comparisons=comparisons,
        comparison_integrity_warning=comparison_warning,
    )
    assert payload["diagnostic"]["status"] == "stable_across_checkpoints"
    assert payload["graph"]["edge_count"] > 3
    assert "demo-token" not in json.dumps(payload["graph"])
    assert payload["candidates"][0]["status"] == "pending"
    assert payload["comparisons"][0]["review_status"] == "needs_review"
    assert payload["comparisons"][0]["components"]

    restricted = loader.load("demo-restricted")
    restricted_payload = case_details(restricted)
    assert restricted_payload["content_usable"] is False
    assert restricted_payload["entities"] == []
    assert restricted_payload["candidates"] == []

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        build_demo(result.output_directory)


def test_demo_cli_creates_a_new_offline_walkthrough(tmp_path: Path) -> None:
    output = tmp_path / "demo-cli"
    completed = subprocess.run(
        [sys.executable, "-m", "hawkeye", "demo", "--output", str(output)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(completed.stdout)
    assert summary["status"] == "completed"
    assert Path(summary["cases_directory"]).is_dir()
    assert Path(summary["comparisons_directory"]).is_dir()
    assert Path(summary["comparison_path"]).is_file()
