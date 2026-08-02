"""G0 evaluation manifests and read-only report generation tests."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from hawkeye.collector.safety import SafetyPolicy
from hawkeye.evaluation import EvaluationInputError, evaluate_case, load_manifest
from hawkeye.pipeline import investigate


def _policy_fixture(root: Path) -> tuple[Path, str]:
    fixture = root / "evaluation" / "fixtures" / "policy.json"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text('{"schema_version":"1.0"}\n', encoding="utf-8")
    return fixture, hashlib.sha256(fixture.read_bytes()).hexdigest()


def _manifest(root: Path, *, input_url: str, fixture_sha256: str) -> Path:
    path = root / "evaluation" / "manifests" / "fixture-evaluation.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "evaluation_id": "fixture-evaluation-001",
        "input_url": input_url,
        "purpose": "Deterministic local evaluation only.",
        "source_type": "public_web",
        "live_evaluation": True,
        "collection_policy": {
            "interactive": False,
            "max_depth": 1,
            "max_pages": 5,
            "candidate_crawling": False,
        },
        "fixture_manifest_path": "evaluation/fixtures/policy.json",
        "fixture_manifest_sha256": fixture_sha256,
        "expected_invariants": [
            {"id": "navigation_attempted", "operator": "equals", "value": True},
            {"id": "artifacts_preserved", "operator": "equals", "value": True},
            {"id": "max_pages", "operator": "less_or_equal", "value": 5},
            {"id": "max_depth", "operator": "less_or_equal", "value": 1},
            {"id": "external_documents_crawled", "operator": "equals", "value": 0},
            {"id": "candidate_domains_crawled", "operator": "equals", "value": 0},
            {"id": "review_status", "operator": "equals", "value": "needs_review"},
        ],
        "environmental_restrictions": ["Synthetic local fixture; no live navigation is involved."],
    }
    path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")
    return path


def _completed_case(fixture_server_url: str, root: Path) -> Path:
    result = investigate(
        fixture_server_url,
        output=root / "cases",
        case_id="fixture-evaluation-case",
        timeout_seconds=15,
        safety_policy=SafetyPolicy(allow_loopback_for_testing=True),
    )
    assert result.case.status == "completed", result.case.error
    return Path(result.case_directory)


def test_checked_in_live_manifests_verify_the_shared_fixture_hash() -> None:
    repository_root = Path(__file__).parents[1]
    manifests = sorted((repository_root / "evaluation" / "manifests").glob("*.json"))

    assert [path.name for path in manifests] == [
        "live-qq101xfw-001.json",
        "live-qq888bet4cv-001.json",
    ]
    loaded = [load_manifest(path) for path in manifests]

    assert all(item.manifest.live_evaluation for item in loaded)
    assert all(item.manifest.collection_policy.interactive is False for item in loaded)
    assert all(item.manifest.collection_policy.candidate_crawling is False for item in loaded)
    assert all(item.fixture_path.is_file() for item in loaded)


def test_evaluation_report_is_read_only_hash_backed_and_non_overwriting(
    fixture_server_url: str, tmp_path: Path
) -> None:
    fixture, fixture_sha256 = _policy_fixture(tmp_path)
    case_directory = _completed_case(fixture_server_url, tmp_path)
    manifest = _manifest(tmp_path, input_url=fixture_server_url, fixture_sha256=fixture_sha256)
    report_path = tmp_path / "reports" / "fixture-report.json"

    result = evaluate_case(manifest, case_directory, report_path)

    assert fixture.is_file()
    assert result.report_path == report_path.resolve()
    assert result.report.passed is True
    assert result.report.git_commit is not None
    assert len(result.report.artifact_sha256) >= 2
    assert all(item.passed for item in result.report.observed_invariants)
    serialized = json.loads(report_path.read_text(encoding="utf-8"))
    assert serialized["source_case_id"] == "fixture-evaluation-case"
    assert serialized["artifact_sha256"] == result.report.artifact_sha256

    with pytest.raises(FileExistsError):
        evaluate_case(manifest, case_directory, report_path)


def test_evaluation_rejects_tampered_fixture_policy_or_mismatched_case(
    fixture_server_url: str, tmp_path: Path
) -> None:
    fixture, fixture_sha256 = _policy_fixture(tmp_path)
    case_directory = _completed_case(fixture_server_url, tmp_path)
    manifest = _manifest(tmp_path, input_url=fixture_server_url, fixture_sha256=fixture_sha256)
    fixture.write_text('{"schema_version":"tampered"}\n', encoding="utf-8")

    with pytest.raises(EvaluationInputError, match="SHA-256"):
        evaluate_case(manifest, case_directory, tmp_path / "report.json")

    fixture, fixture_sha256 = _policy_fixture(tmp_path)
    manifest = _manifest(
        tmp_path, input_url="https://different.example/", fixture_sha256=fixture_sha256
    )
    with pytest.raises(EvaluationInputError, match="seed URL"):
        evaluate_case(manifest, case_directory, tmp_path / "mismatched-report.json")


def test_evaluate_cli_uses_only_the_completed_local_case(
    fixture_server_url: str, tmp_path: Path
) -> None:
    _, fixture_sha256 = _policy_fixture(tmp_path)
    case_directory = _completed_case(fixture_server_url, tmp_path)
    manifest = _manifest(tmp_path, input_url=fixture_server_url, fixture_sha256=fixture_sha256)
    report_path = tmp_path / "reports" / "cli-report.json"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "hawkeye",
            "evaluate",
            str(manifest),
            str(case_directory),
            "--report",
            str(report_path),
        ],
        check=False,
        capture_output=True,
        env=os.environ.copy(),
        text=True,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(completed.stdout)
    assert summary["status"] == "completed"
    assert summary["passed"] is True
    assert report_path.is_file()


def test_delayed_script_render_fixture_reproduces_the_current_completeness_gap(
    fixture_server_url: str, tmp_path: Path
) -> None:
    result = investigate(
        f"{fixture_server_url}delayed-script-render-shell.html",
        output=tmp_path / "cases",
        case_id="delayed-shell-case",
        timeout_seconds=15,
        safety_policy=SafetyPolicy(allow_loopback_for_testing=True),
    )

    assert result.case.status == "completed", result.case.error
    html = (Path(result.case_directory) / "pages" / "page-001.html").read_text(encoding="utf-8")
    visible_text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    assert "Initial local shell." in visible_text
    assert "Delayed synthetic rendered content." not in visible_text


def test_delayed_script_render_fixture_metadata_is_local_and_explicit() -> None:
    repository_root = Path(__file__).parents[1]
    metadata = json.loads(
        (
            repository_root / "evaluation" / "fixtures" / "delayed-script-render-shell-v1.json"
        ).read_text(encoding="utf-8")
    )
    html = (repository_root / "tests" / "fixtures" / "delayed_script_render_shell.html").read_text(
        encoding="utf-8"
    )

    assert metadata == {
        "current_expected_behavior": "Capture may contain only the initial shell",
        "engine_behavior_changed": False,
        "fixture_id": "delayed-script-render-shell-v1",
        "future_review_target": (
            "Determine whether bounded render-readiness handling improves evidence completeness"
        ),
        "network_access": False,
        "purpose": "Reproduce a page whose initial document is sparse before client-side rendering",
        "scenario": "delayed_script_render_shell",
        "schema_version": "1.0",
    }
    assert "http://" not in html
    assert "https://" not in html
    assert "<script src" not in html
