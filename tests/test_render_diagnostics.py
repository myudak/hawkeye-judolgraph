"""G1 fixed-time, zero-network rendered-content diagnostic coverage."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hawkeye.collector.safety import SafetyPolicy
from hawkeye.diagnostics import DiagnosticInputError, run_render_diagnostics
from hawkeye.diagnostics.models import RenderDiagnosticsDocument
from hawkeye.pipeline import investigate

_SCENARIOS = [
    ("render-static-complete.html", "stable_across_checkpoints"),
    ("render-shell-500.html", "changed_after_initial_capture"),
    ("render-shell-1500.html", "changed_after_initial_capture"),
    ("render-continuing.html", "continued_changing_at_budget_end"),
    ("render-sparse-blank.html", "low_information_across_checkpoints"),
    ("render-canvas-heavy.html", "stable_across_checkpoints"),
    ("render-dom-growth-static.html", "changed_after_initial_capture"),
    ("render-visual-change-static-dom.html", "changed_after_initial_capture"),
]


def _collect_fixture_case(fixture_server_url: str, root: Path, fixture_path: str) -> Path:
    result = investigate(
        f"{fixture_server_url}{fixture_path}",
        output=root / "cases",
        case_id=f"diagnostic-{fixture_path.removesuffix('.html')}",
        timeout_seconds=15,
        safety_policy=SafetyPolicy(allow_loopback_for_testing=True),
    )
    assert result.case.status == "completed", result.case.error
    return Path(result.case_directory)


@pytest.mark.parametrize(("fixture_path", "expected_status"), _SCENARIOS)
def test_fixed_time_diagnostics_capture_expected_local_relationships(
    fixture_server_url: str,
    tmp_path: Path,
    fixture_path: str,
    expected_status: str,
) -> None:
    case_directory = _collect_fixture_case(fixture_server_url, tmp_path, fixture_path)
    canonical_before = {
        filename: (case_directory / filename).read_bytes()
        for filename in ("case.json", "pages.json", "evidence.json", "entities.json", "graph.json")
    }

    result = run_render_diagnostics(
        case_directory,
        mode="fixture",
        safety_policy=SafetyPolicy(allow_loopback_for_testing=True),
    )

    document = result.document
    assert result.path == case_directory / "diagnostics" / "render-diagnostics.json"
    assert document.status == expected_status
    assert document.collection_mode == "fixture"
    assert document.checkpoint_schedule_ms == [0, 500, 1500, 3000]
    assert document.diagnostic_wait_budget_ms == 3000
    assert [item.elapsed_ms for item in document.checkpoints] == [0, 500, 1500, 3000]
    assert len(document.deltas) == 3
    assert {item.type for item in document.source_evidence_refs} == {"html_page", "screenshot"}
    assert all(item.sha256 for item in document.source_evidence_refs)
    assert all(item.document_ready_state == "complete" for item in document.checkpoints)
    assert all(
        (case_directory / filename).read_bytes() == content
        for filename, content in canonical_before.items()
    )

    _assert_scenario_relationships(fixture_path, document)
    serialized = RenderDiagnosticsDocument.model_validate_json(
        result.path.read_text(encoding="utf-8")
    )
    assert serialized == document


def _assert_scenario_relationships(fixture_path: str, document: RenderDiagnosticsDocument) -> None:
    if fixture_path in {"render-shell-500.html", "render-shell-1500.html"}:
        assert any(delta.visible_text_chars_delta > 0 for delta in document.deltas)
        assert any(delta.element_count_delta > 0 for delta in document.deltas)
    elif fixture_path == "render-continuing.html":
        assert document.deltas[-1].element_count_delta > 0
    elif fixture_path == "render-sparse-blank.html":
        assert all(item.visible_text_chars == 0 for item in document.checkpoints)
        assert all(item.screenshot_entropy <= 0.25 for item in document.checkpoints)
    elif fixture_path == "render-canvas-heavy.html":
        assert all(item.canvas_count == 1 for item in document.checkpoints)
        assert all(item.screenshot_entropy > 0.25 for item in document.checkpoints)
    elif fixture_path == "render-dom-growth-static.html":
        dom_delta = next(delta for delta in document.deltas if delta.element_count_delta > 0)
        assert dom_delta.screenshot_changed is False
    elif fixture_path == "render-visual-change-static-dom.html":
        assert any(delta.screenshot_changed for delta in document.deltas)
        assert all(delta.element_count_delta == 0 for delta in document.deltas)
        assert all(delta.html_bytes_delta == 0 for delta in document.deltas)


def test_diagnostics_refuse_to_overwrite_or_leave_case_scope(
    fixture_server_url: str, tmp_path: Path
) -> None:
    case_directory = _collect_fixture_case(
        fixture_server_url, tmp_path, "render-static-complete.html"
    )
    run_render_diagnostics(
        case_directory,
        mode="fixture",
        safety_policy=SafetyPolicy(allow_loopback_for_testing=True),
    )

    with pytest.raises(FileExistsError):
        run_render_diagnostics(
            case_directory,
            mode="fixture",
            safety_policy=SafetyPolicy(allow_loopback_for_testing=True),
        )
    with pytest.raises(DiagnosticInputError, match="page ID"):
        run_render_diagnostics(
            case_directory,
            page_id="page-999",
            mode="fixture",
            safety_policy=SafetyPolicy(allow_loopback_for_testing=True),
        )


def test_diagnostics_require_mode_matched_loopback_policy(
    fixture_server_url: str, tmp_path: Path
) -> None:
    case_directory = _collect_fixture_case(
        fixture_server_url, tmp_path, "render-static-complete.html"
    )

    with pytest.raises(DiagnosticInputError, match="Fixture diagnostics require"):
        run_render_diagnostics(case_directory, mode="fixture")
    with pytest.raises(DiagnosticInputError, match="Live diagnostics must not"):
        run_render_diagnostics(
            case_directory,
            mode="live",
            safety_policy=SafetyPolicy(allow_loopback_for_testing=True),
        )


def test_diagnose_cli_is_opt_in_and_uses_the_fixed_artifact_path(
    fixture_server_url: str, tmp_path: Path
) -> None:
    case_directory = _collect_fixture_case(
        fixture_server_url, tmp_path, "render-static-complete.html"
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "hawkeye",
            "diagnose",
            str(case_directory),
            "--mode",
            "fixture",
            "--allow-loopback-for-testing",
        ],
        check=False,
        capture_output=True,
        env={**os.environ, "HAWKEYE_TEST_MODE": "1"},
        text=True,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(completed.stdout)
    assert summary["status"] == "stable_across_checkpoints"
    assert Path(summary["diagnostics_path"]).is_file()


def test_diagnose_cli_rejects_fixture_mode_without_loopback_opt_in(
    fixture_server_url: str, tmp_path: Path
) -> None:
    case_directory = _collect_fixture_case(
        fixture_server_url, tmp_path, "render-static-complete.html"
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "hawkeye",
            "diagnose",
            str(case_directory),
            "--mode",
            "fixture",
        ],
        check=False,
        capture_output=True,
        env=os.environ.copy(),
        text=True,
    )

    assert completed.returncode == 2
    assert "Fixture diagnostics require" in completed.stdout
