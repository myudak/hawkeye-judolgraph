"""Local fixture-server end-to-end coverage, including the public CLI path."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hawkeye.collector.safety import SafetyPolicy
from hawkeye.models import CaptureOutcome
from hawkeye.pipeline import investigate


def test_local_fixture_server_creates_complete_evidence_case(
    fixture_server_url: str, tmp_path: Path
) -> None:
    result = investigate(
        fixture_server_url,
        output=tmp_path / "cases",
        case_id="fixture-case",
        timeout_seconds=15,
        safety_policy=SafetyPolicy(allow_loopback_for_testing=True),
    )

    assert result.case.status == "completed", result.case.error
    assert result.case.navigation_status == "captured"
    assert result.case.capture_outcome is CaptureOutcome.CONTENT
    assert result.case.content_usable is True
    case_root = Path(result.case_directory)
    assert (case_root / "pages" / "page-001.html").is_file()
    assert (case_root / "screenshots" / "page-001.png").is_file()
    assert (case_root / "evidence.json").is_file()
    assert (case_root / "entities.json").is_file()
    assert (case_root / "graph.json").is_file()
    assert (case_root / "run.log").is_file()

    evidence = json.loads((case_root / "evidence.json").read_text(encoding="utf-8"))
    graph = json.loads((case_root / "graph.json").read_text(encoding="utf-8"))
    entities = json.loads((case_root / "entities.json").read_text(encoding="utf-8"))
    evidence_ids = {record["id"] for record in evidence}
    assert {record["type"] for record in evidence} >= {
        "html_page",
        "screenshot",
        "visible_text",
        "response_metadata",
        "capture_readiness",
        "full_page_screenshot",
    }
    assert any(entity["type"] == "telegram" for entity in entities)
    assert any(entity["type"] == "whatsapp_or_phone" for entity in entities)
    for edge in graph["edges"]:
        if edge["type"] not in {"started_from", "resolved_to", "contains_page", "captured_as"}:
            assert edge["evidence_id"] in evidence_ids
            assert edge["source_url"]
            assert edge["extraction_method"]
            assert edge["confidence"] == 1.0


def test_records_redirect_chain_and_final_url(fixture_server_url: str, tmp_path: Path) -> None:
    result = investigate(
        f"{fixture_server_url}redirect",
        output=tmp_path / "cases",
        case_id="redirect-case",
        timeout_seconds=15,
        safety_policy=SafetyPolicy(allow_loopback_for_testing=True),
    )

    assert result.case.status == "completed", result.case.error
    assert result.case.final_url == fixture_server_url
    assert result.case.redirect_chain == [f"{fixture_server_url}redirect"]
    assert result.case.redirects[0].source_url == f"{fixture_server_url}redirect"
    assert result.case.redirects[0].destination_url == fixture_server_url
    assert result.case.redirects[0].status_code == 302
    assert result.pages[0].redirect_evidence_id == "evidence-network-001"
    evidence = json.loads(
        (Path(result.case_directory) / "evidence.json").read_text(encoding="utf-8")
    )
    assert any(record["type"] == "network_event" for record in evidence)


@pytest.mark.parametrize(
    ("path", "outcome"),
    [
        ("unavailable-page.html", CaptureOutcome.UNAVAILABLE_PAGE),
        ("bot-challenge.html", CaptureOutcome.BOT_CHALLENGE),
        ("consent-wall.html", CaptureOutcome.CONSENT_WALL),
    ],
)
def test_unusable_fixture_pages_preserve_artifacts_without_target_entities(
    fixture_server_url: str, tmp_path: Path, path: str, outcome: CaptureOutcome
) -> None:
    result = investigate(
        f"{fixture_server_url}{path}",
        output=tmp_path / "cases",
        case_id=f"{outcome.value}-case",
        timeout_seconds=15,
        safety_policy=SafetyPolicy(allow_loopback_for_testing=True),
    )

    assert result.case.status == "completed", result.case.error
    assert result.case.capture_outcome is outcome
    assert result.case.content_usable is False
    case_root = Path(result.case_directory)
    assert (case_root / "pages" / "page-001.html").is_file()
    assert (case_root / "screenshots" / "page-001.png").is_file()
    assert json.loads((case_root / "entities.json").read_text(encoding="utf-8")) == []
    graph = json.loads((case_root / "graph.json").read_text(encoding="utf-8"))
    assert {edge["type"] for edge in graph["edges"]} == {
        "started_from",
        "contains_page",
        "captured_as",
    }


def test_cli_local_fixture_demonstration(fixture_server_url: str, tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "hawkeye",
            "investigate",
            fixture_server_url,
            "--output",
            str(tmp_path / "cli-cases"),
            "--case-id",
            "cli-fixture-case",
            "--timeout",
            "15",
            "--allow-loopback-for-testing",
        ],
        check=False,
        capture_output=True,
        env={**os.environ, "HAWKEYE_TEST_MODE": "1"},
        text=True,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(completed.stdout)
    assert summary["status"] == "completed"
    assert Path(summary["case_directory"]).joinpath("graph.json").is_file()


def test_cli_rejects_loopback_test_override_without_test_mode(
    fixture_server_url: str, tmp_path: Path
) -> None:
    environment = dict(os.environ)
    environment.pop("HAWKEYE_TEST_MODE", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "hawkeye",
            "investigate",
            fixture_server_url,
            "--output",
            str(tmp_path / "cli-cases"),
            "--allow-loopback-for-testing",
        ],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert completed.returncode == 2
    assert "HAWKEYE_TEST_MODE=1" in completed.stdout
