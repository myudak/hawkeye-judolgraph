"""G4A canonical capture-adequacy and artifact preservation tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hawkeye.collector.safety import SafetyPolicy
from hawkeye.models import AccessOutcome, CaptureAdequacy, PublicCaptureStatus
from hawkeye.pipeline import investigate


def _capture(fixture_server_url: str, tmp_path: Path, path: str) -> tuple[object, Path]:
    result = investigate(
        f"{fixture_server_url}{path}",
        output=tmp_path / "cases",
        case_id=path.replace(".html", "").replace("-", "_")[:70],
        timeout_seconds=15,
        case_timeout_seconds=30,
        max_pages=1,
        max_depth=0,
        safety_policy=SafetyPolicy(allow_loopback_for_testing=True),
    )
    assert result.case.status == "completed", result.case.error
    return result, Path(result.case_directory)


def test_delayed_render_uses_final_canonical_state_and_preserves_initial(
    fixture_server_url: str, tmp_path: Path
) -> None:
    result, root = _capture(fixture_server_url, tmp_path, "render-shell-1500.html")
    page = result.pages[0]
    readiness = json.loads((root / "capture/page-001-readiness.json").read_text("utf-8"))
    assert [item["elapsed_ms"] for item in readiness["checkpoints"]] == [0, 500, 1500, 3000]
    assert (
        readiness["checkpoints"][0]["visible_text_chars"]
        < readiness["checkpoints"][-1]["visible_text_chars"]
    )
    assert page.initial_screenshot_evidence_id is not None
    assert page.capture_adequacy is CaptureAdequacy.ADEQUATE
    assert page.extraction_eligible is True


@pytest.mark.parametrize(
    ("path", "access", "adequacy", "public_status", "extraction_eligible"),
    [
        (
            "render-rich-hidden-blank.html",
            AccessOutcome.UNKNOWN_RESTRICTION,
            CaptureAdequacy.LIMITED,
            PublicCaptureStatus.CAPTURED_WITH_LIMITATIONS,
            False,
        ),
        (
            "render-continuing.html",
            AccessOutcome.CONTENT,
            CaptureAdequacy.ADEQUATE,
            PublicCaptureStatus.CAPTURED,
            True,
        ),
        (
            "render-never-settles.html",
            AccessOutcome.CONTENT,
            CaptureAdequacy.LIMITED,
            PublicCaptureStatus.CAPTURED_WITH_LIMITATIONS,
            True,
        ),
        (
            "geo-restriction-wording.html",
            AccessOutcome.GEO_RESTRICTION,
            CaptureAdequacy.ADEQUATE,
            PublicCaptureStatus.GEO_RESTRICTION_OBSERVED,
            False,
        ),
        (
            "unavailable-by-location.html",
            AccessOutcome.UNAVAILABLE,
            CaptureAdequacy.ADEQUATE,
            PublicCaptureStatus.UNAVAILABLE,
            False,
        ),
        (
            "blank-access-challenge.html",
            AccessOutcome.ACCESS_CHALLENGE,
            CaptureAdequacy.LIMITED,
            PublicCaptureStatus.ACCESS_CHALLENGE_OBSERVED,
            False,
        ),
    ],
)
def test_capture_dimensions_are_independent(
    fixture_server_url: str,
    tmp_path: Path,
    path: str,
    access: AccessOutcome,
    adequacy: CaptureAdequacy,
    public_status: PublicCaptureStatus,
    extraction_eligible: bool,
) -> None:
    result, _ = _capture(fixture_server_url, tmp_path, path)
    page = result.pages[0]
    assert page.navigation_status == "captured"
    assert page.access_outcome is access
    assert page.capture_adequacy is adequacy
    assert page.public_status is public_status
    assert page.extraction_eligible is extraction_eligible


def test_html_between_two_and_five_megabytes_is_persisted_but_not_extracted(
    fixture_server_url: str, tmp_path: Path
) -> None:
    result, root = _capture(fixture_server_url, tmp_path, "oversized-dom-2mb.html")
    page = result.pages[0]
    readiness = json.loads((root / "capture/page-001-readiness.json").read_text("utf-8"))
    assert 2_000_000 < readiness["html_bytes"] <= 5_000_000
    assert (root / "pages/page-001.html").is_file()
    assert page.capture_adequacy is CaptureAdequacy.ADEQUATE
    assert page.extraction_eligible is False
    assert page.extraction_skip_reason == "direct_extractor_input_exceeds_2_mb"


def test_html_above_five_megabytes_keeps_partial_evidence_without_navigation_failure(
    fixture_server_url: str, tmp_path: Path
) -> None:
    result, root = _capture(fixture_server_url, tmp_path, "oversized-dom-5mb.html")
    page = result.pages[0]
    readiness = json.loads((root / "capture/page-001-readiness.json").read_text("utf-8"))
    assert readiness["html_bytes"] > 5_000_000
    assert readiness["html_sha256"]
    assert not (root / "pages/page-001.html").exists()
    assert (root / "pages/page-001-visible.txt").is_file()
    assert (root / "screenshots/page-001.png").is_file()
    assert page.navigation_status == "captured"
    assert page.capture_adequacy is CaptureAdequacy.LIMITED
    assert page.extraction_skip_reason == "canonical_html_not_persisted"


def test_long_page_is_bounded_and_canvas_can_be_adequate_visual_evidence(
    fixture_server_url: str, tmp_path: Path
) -> None:
    long_result, long_root = _capture(fixture_server_url, tmp_path, "render-long-page.html")
    long_readiness = json.loads((long_root / "capture/page-001-readiness.json").read_text("utf-8"))
    assert "full_page_truncated_at_12000_px" in long_readiness["limitation_reasons"]
    assert long_result.pages[0].full_page_screenshot_evidence_id is not None

    canvas_result, _ = _capture(fixture_server_url, tmp_path, "render-canvas-heavy.html")
    assert canvas_result.pages[0].capture_adequacy is CaptureAdequacy.ADEQUATE


def test_opaque_splash_over_rich_dom_is_limited_and_not_extracted(
    fixture_server_url: str, tmp_path: Path
) -> None:
    result, root = _capture(fixture_server_url, tmp_path, "render-opaque-splash-rich-dom.html")
    page = result.pages[0]
    readiness = json.loads((root / "capture/page-001-readiness.json").read_text("utf-8"))

    assert readiness["checkpoints"][-1]["visible_text_chars"] >= 1_000
    assert readiness["checkpoints"][-1]["informative_tile_ratio"] < 0.10
    assert "visual_dom_mismatch" in readiness["limitation_reasons"]
    assert page.capture_adequacy is CaptureAdequacy.LIMITED
    assert page.extraction_eligible is False
