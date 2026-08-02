"""Offline V0.3 comparison tests using self-contained, integrity-checked local cases."""

from __future__ import annotations

import hashlib
import json
import shutil
import socket
import subprocess
import sys
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from hawkeye.comparison import ComparisonInputError, compare_cases, write_comparison
from hawkeye.models import (
    CaptureOutcome,
    CaseRecord,
    CrawlPageRecord,
    EvidenceRecord,
    ExtractedEntity,
)

NOW = datetime(2026, 8, 2, tzinfo=UTC)


def _write_case(
    root: Path,
    *,
    case_id: str,
    url: str,
    html: str,
    screenshot_variant: str,
    entities: list[tuple[str, str]],
) -> Path:
    directory = root / case_id
    pages_directory = directory / "pages"
    screenshots_directory = directory / "screenshots"
    pages_directory.mkdir(parents=True)
    screenshots_directory.mkdir()
    html_bytes = html.encode()
    screenshot_bytes = _screenshot(screenshot_variant)
    html_path = pages_directory / "page-001.html"
    screenshot_path = screenshots_directory / "page-001.png"
    html_path.write_bytes(html_bytes)
    screenshot_path.write_bytes(screenshot_bytes)
    html_evidence = EvidenceRecord(
        id="evidence-page-001",
        type="html_page",
        source_url=url,
        path="pages/page-001.html",
        collected_at=NOW,
        sha256=hashlib.sha256(html_bytes).hexdigest(),
        page_id="page-001",
    )
    screenshot_evidence = EvidenceRecord(
        id="evidence-screenshot-001",
        type="screenshot",
        source_url=url,
        path="screenshots/page-001.png",
        collected_at=NOW,
        sha256=hashlib.sha256(screenshot_bytes).hexdigest(),
        page_id="page-001",
        viewport={"width": 64, "height": 64},
        image_dimensions={"width": 64, "height": 64},
    )
    case = CaseRecord(
        case_id=case_id,
        seed_url=url,
        final_url=url,
        status="completed",
        started_at=NOW,
        completed_at=NOW,
        navigation_status="captured",
        capture_outcome=CaptureOutcome.CONTENT,
        content_usable=True,
        page_count=1,
    )
    page = CrawlPageRecord(
        id="page-001",
        url=url,
        normalized_url=url,
        depth=0,
        state="completed",
        final_url=url,
        navigation_status="captured",
        capture_outcome=CaptureOutcome.CONTENT,
        content_usable=True,
        html_evidence_id=html_evidence.id,
        screenshot_evidence_id=screenshot_evidence.id,
        content_sha256=html_evidence.sha256,
    )
    extracted = [
        ExtractedEntity(
            id=f"entity-{index:03d}",
            type=entity_type,
            value=value,
            normalized_value=value,
            source_evidence_id=html_evidence.id,
            source_url=url,
            extraction_method="fixture",
            confidence=1.0,
        )
        for index, (entity_type, value) in enumerate(entities, start=1)
    ]
    payloads = {
        "case.json": case.model_dump(mode="json"),
        "pages.json": [page.model_dump(mode="json")],
        "evidence.json": [
            html_evidence.model_dump(mode="json"),
            screenshot_evidence.model_dump(mode="json"),
        ],
        "entities.json": [entity.model_dump(mode="json") for entity in extracted],
    }
    for name, payload in payloads.items():
        (directory / name).write_text(
            f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8"
        )
    return directory


def _append_page(
    directory: Path,
    *,
    page_id: str,
    url: str,
    html: str,
    screenshot_variant: str,
) -> None:
    """Add a completed fixture page so aggregation behavior is tested end to end."""

    html_bytes = html.encode()
    screenshot_bytes = _screenshot(screenshot_variant)
    html_path = directory / "pages" / f"{page_id}.html"
    screenshot_path = directory / "screenshots" / f"{page_id}.png"
    html_path.write_bytes(html_bytes)
    screenshot_path.write_bytes(screenshot_bytes)
    suffix = page_id.removeprefix("page-")
    html_evidence = EvidenceRecord(
        id=f"evidence-page-{suffix}",
        type="html_page",
        source_url=url,
        path=f"pages/{page_id}.html",
        collected_at=NOW,
        sha256=hashlib.sha256(html_bytes).hexdigest(),
        page_id=page_id,
    )
    screenshot_evidence = EvidenceRecord(
        id=f"evidence-screenshot-{suffix}",
        type="screenshot",
        source_url=url,
        path=f"screenshots/{page_id}.png",
        collected_at=NOW,
        sha256=hashlib.sha256(screenshot_bytes).hexdigest(),
        page_id=page_id,
        viewport={"width": 64, "height": 64},
        image_dimensions={"width": 64, "height": 64},
    )
    page = CrawlPageRecord(
        id=page_id,
        url=url,
        normalized_url=url,
        depth=1,
        state="completed",
        final_url=url,
        navigation_status="captured",
        capture_outcome=CaptureOutcome.CONTENT,
        content_usable=True,
        html_evidence_id=html_evidence.id,
        screenshot_evidence_id=screenshot_evidence.id,
        content_sha256=html_evidence.sha256,
    )
    pages = json.loads((directory / "pages.json").read_text(encoding="utf-8"))
    evidence = json.loads((directory / "evidence.json").read_text(encoding="utf-8"))
    pages.append(page.model_dump(mode="json"))
    evidence.extend(
        (html_evidence.model_dump(mode="json"), screenshot_evidence.model_dump(mode="json"))
    )
    case = CaseRecord.model_validate(
        json.loads((directory / "case.json").read_text(encoding="utf-8"))
    ).model_copy(update={"page_count": len(pages)})
    (directory / "case.json").write_text(
        f"{json.dumps(case.model_dump(mode='json'), indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )
    (directory / "pages.json").write_text(
        f"{json.dumps(pages, indent=2, sort_keys=True)}\n", encoding="utf-8"
    )
    (directory / "evidence.json").write_text(
        f"{json.dumps(evidence, indent=2, sort_keys=True)}\n", encoding="utf-8"
    )


def _screenshot(variant: str) -> bytes:
    image = Image.new("L", (64, 64), color=255)
    draw = ImageDraw.Draw(image)
    if variant == "left":
        draw.rectangle((0, 0, 31, 63), fill=0)
    elif variant == "right":
        draw.rectangle((32, 0, 63, 63), fill=0)
    elif variant != "plain":
        raise ValueError(f"Unknown screenshot variant: {variant}")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _component(document: object, name: str) -> object:
    return next(component for component in document.components if component.name == name)


def test_identical_cases_have_fully_explainable_offline_similarity(tmp_path: Path) -> None:
    root = tmp_path / "cases"
    html = """
    <!doctype html><html><head><title>Fixture</title></head>
    <body><main><h1>Shared fixture heading</h1><p>Same visible body words.</p></main></body></html>
    """
    entities = [
        ("telegram", "@sharedadmin"),
        ("external_asset_url", "https://assets.example.net/app.js"),
    ]
    left = _write_case(
        root,
        case_id="left-case",
        url="https://left.example.com/",
        html=html,
        screenshot_variant="left",
        entities=entities,
    )
    right = _write_case(
        root,
        case_id="right-case",
        url="https://right.example.net/",
        html=html,
        screenshot_variant="left",
        entities=entities,
    )

    document = compare_cases(left, right)

    assert document.review_status == "needs_review"
    assert document.candidate_mirror_score == 100.0
    assert all(component.score == 1.0 for component in document.components)
    entities_component = _component(document, "shared_entity_similarity")
    assert {(ref.case_id, ref.evidence_id) for ref in entities_component.entity_refs} == {
        ("left-case", "evidence-page-001"),
        ("right-case", "evidence-page-001"),
    }
    for reference in entities_component.evidence_refs:
        case_root = left if reference.case_id == "left-case" else right
        assert (case_root / reference.path).is_file()


def test_dissimilar_cases_keep_each_component_separate_and_do_not_claim_ownership(
    tmp_path: Path,
) -> None:
    root = tmp_path / "cases"
    left = _write_case(
        root,
        case_id="left-case",
        url="https://left.example.com/",
        html="<html><body><main><h1>Alpha content</h1><p>first words only</p></main></body></html>",
        screenshot_variant="left",
        entities=[("telegram", "@alphaadmin")],
    )
    right = _write_case(
        root,
        case_id="right-case",
        url="https://right.example.net/",
        html="<html><body><footer><ul><li>different content</li></ul></footer></body></html>",
        screenshot_variant="right",
        entities=[("referral", "affiliate=DIFFERENT")],
    )

    document = compare_cases(left, right)

    assert document.review_status == "needs_review"
    assert document.candidate_mirror_score < 50
    assert _component(document, "shared_entity_similarity").score == 0.0
    assert _component(document, "shared_asset_similarity").available is False
    assert _component(document, "screenshot_perceptual_similarity").score < 1.0


def test_empty_or_suppressed_entities_never_contribute_a_perfect_score(tmp_path: Path) -> None:
    root = tmp_path / "cases"
    html = """
    <html><body><main><h1>Enough visible words for a valid text comparison</h1>
    <p>with stable structure and a nonblank screenshot.</p></main></body></html>
    """
    suppressed = [
        ("referral", "ref=default"),
        ("external_asset_url", "https://cdnjs.cloudflare.com/library.js"),
    ]
    left = _write_case(
        root,
        case_id="left-case",
        url="https://left.example.com/",
        html=html,
        screenshot_variant="left",
        entities=suppressed,
    )
    right = _write_case(
        root,
        case_id="right-case",
        url="https://right.example.net/",
        html=html,
        screenshot_variant="left",
        entities=suppressed,
    )

    document = compare_cases(left, right)

    entity_component = _component(document, "shared_entity_similarity")
    asset_component = _component(document, "shared_asset_similarity")
    assert entity_component.score == 0.0
    assert entity_component.status == "not_applicable"
    assert asset_component.score == 0.0
    assert asset_component.status == "not_applicable"
    assert document.candidate_mirror_score < 100.0


def test_one_sided_entity_evidence_scores_zero_instead_of_not_applicable(tmp_path: Path) -> None:
    root = tmp_path / "cases"
    html = "<html><body><p>enough visible body words appear in fixture page</p></body></html>"
    left = _write_case(
        root,
        case_id="left-case",
        url="https://left.example.com/",
        html=html,
        screenshot_variant="left",
        entities=[("telegram", "@onlyleft")],
    )
    right = _write_case(
        root,
        case_id="right-case",
        url="https://right.example.net/",
        html=html,
        screenshot_variant="left",
        entities=[],
    )

    component = _component(compare_cases(left, right), "shared_entity_similarity")

    assert component.available is True
    assert component.status == "scored"
    assert component.score == 0.0


def test_blank_screenshots_are_marked_low_information(tmp_path: Path) -> None:
    root = tmp_path / "cases"
    html = "<html><body><p>enough visible body words appear in this fixture page</p></body></html>"
    left = _write_case(
        root,
        case_id="left-case",
        url="https://left.example.com/",
        html=html,
        screenshot_variant="plain",
        entities=[],
    )
    right = _write_case(
        root,
        case_id="right-case",
        url="https://right.example.net/",
        html=html,
        screenshot_variant="plain",
        entities=[],
    )

    component = _component(compare_cases(left, right), "screenshot_perceptual_similarity")

    assert component.available is False
    assert component.status == "low_information"
    assert component.score == 0.0
    assert component.details["page_pairs"][0]["left_pixel_variance"] == 0.0


def test_page_aggregation_deduplicates_content_and_penalizes_unmatched_pages(
    tmp_path: Path,
) -> None:
    root = tmp_path / "cases"
    base_html = """
    <html><body><main><h1>Enough shared visible words for the fixture page</h1>
    <p>and a stable DOM structure used for deterministic comparison.</p></main></body></html>
    """
    left = _write_case(
        root,
        case_id="left-case",
        url="https://left.example.com/",
        html=base_html,
        screenshot_variant="left",
        entities=[],
    )
    right = _write_case(
        root,
        case_id="right-case",
        url="https://right.example.net/",
        html=base_html,
        screenshot_variant="left",
        entities=[],
    )
    _append_page(
        left,
        page_id="page-002",
        url="https://left.example.com/duplicate",
        html=base_html,
        screenshot_variant="left",
    )

    deduplicated = _component(compare_cases(left, right), "visible_text_similarity")

    assert deduplicated.score == 1.0
    assert [pair["left_page_id"] for pair in deduplicated.details["page_pairs"]] == ["page-001"]
    _append_page(
        left,
        page_id="page-003",
        url="https://left.example.com/unique",
        html="""
        <html><body><section><h2>A distinct second page adds unique visible text</h2>
        <p>with enough further words to be scored separately.</p></section></body></html>
        """,
        screenshot_variant="right",
    )

    unmatched = _component(compare_cases(left, right), "visible_text_similarity")

    assert unmatched.status == "scored"
    assert unmatched.score == 0.5
    assert len(unmatched.details["page_pairs"]) == 2
    assert unmatched.details["page_pairs"][1]["right_page_id"] is None
    assert unmatched.details["page_pairs"][1]["score"] == 0.0


def test_comparison_rejects_an_identical_case_manifest_in_a_different_directory(
    tmp_path: Path,
) -> None:
    root = tmp_path / "cases"
    left = _write_case(
        root,
        case_id="left-case",
        url="https://left.example.com/",
        html="<html><body>left</body></html>",
        screenshot_variant="plain",
        entities=[],
    )
    cloned = root / "cloned-case"
    shutil.copytree(left, cloned)

    with pytest.raises(ComparisonInputError, match="identical case manifests"):
        compare_cases(left, cloned)


def test_comparison_rejects_inconsistent_screenshot_metadata(tmp_path: Path) -> None:
    root = tmp_path / "cases"
    left = _write_case(
        root,
        case_id="left-case",
        url="https://left.example.com/",
        html="<html><body>left</body></html>",
        screenshot_variant="plain",
        entities=[],
    )
    right = _write_case(
        root,
        case_id="right-case",
        url="https://right.example.net/",
        html="<html><body>right</body></html>",
        screenshot_variant="plain",
        entities=[],
    )
    evidence = json.loads((right / "evidence.json").read_text(encoding="utf-8"))
    evidence[1]["image_dimensions"] = {"width": 65, "height": 64}
    (right / "evidence.json").write_text(
        f"{json.dumps(evidence, indent=2, sort_keys=True)}\n", encoding="utf-8"
    )

    with pytest.raises(ComparisonInputError, match="image metadata mismatch"):
        compare_cases(left, right)


def test_comparison_rejects_a_modified_evidence_artifact(tmp_path: Path) -> None:
    root = tmp_path / "cases"
    left = _write_case(
        root,
        case_id="left-case",
        url="https://left.example.com/",
        html="<html><body>left</body></html>",
        screenshot_variant="plain",
        entities=[],
    )
    right = _write_case(
        root,
        case_id="right-case",
        url="https://right.example.net/",
        html="<html><body>right</body></html>",
        screenshot_variant="plain",
        entities=[],
    )
    (right / "pages" / "page-001.html").write_text("modified", encoding="utf-8")

    with pytest.raises(ComparisonInputError, match="integrity mismatch"):
        compare_cases(left, right)


def test_comparison_is_semantically_deterministic_and_never_resolves_dns(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "cases"
    left = _write_case(
        root,
        case_id="left-case",
        url="https://left.example.com/",
        html="<html><body><p>same</p></body></html>",
        screenshot_variant="plain",
        entities=[("telegram", "@sharedadmin")],
    )
    right = _write_case(
        root,
        case_id="right-case",
        url="https://right.example.net/",
        html="<html><body><p>same</p></body></html>",
        screenshot_variant="plain",
        entities=[("telegram", "@sharedadmin")],
    )

    def fail_dns(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("comparison must not resolve DNS")

    monkeypatch.setattr(socket, "getaddrinfo", fail_dns)
    first = compare_cases(left, right)
    second = compare_cases(left, right)

    first_payload = first.model_dump(mode="json")
    second_payload = second.model_dump(mode="json")
    first_payload.pop("generated_at")
    second_payload.pop("generated_at")
    assert first_payload == second_payload


def test_cli_writes_a_new_offline_comparison_document(tmp_path: Path) -> None:
    root = tmp_path / "cases"
    left = _write_case(
        root,
        case_id="left-case",
        url="https://left.example.com/",
        html="<html><body><p>same</p></body></html>",
        screenshot_variant="plain",
        entities=[],
    )
    right = _write_case(
        root,
        case_id="right-case",
        url="https://right.example.net/",
        html="<html><body><p>same</p></body></html>",
        screenshot_variant="plain",
        entities=[],
    )
    output = tmp_path / "comparisons" / "comparison.json"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "hawkeye",
            "compare",
            str(left),
            str(right),
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(completed.stdout)
    assert summary["status"] == "completed"
    assert summary["review_status"] == "needs_review"
    assert output.is_file()
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted["schema_version"] == "0.3.0"


def test_write_comparison_refuses_to_overwrite_an_existing_result(tmp_path: Path) -> None:
    root = tmp_path / "cases"
    left = _write_case(
        root,
        case_id="left-case",
        url="https://left.example.com/",
        html="<html><body><p>same</p></body></html>",
        screenshot_variant="plain",
        entities=[],
    )
    right = _write_case(
        root,
        case_id="right-case",
        url="https://right.example.net/",
        html="<html><body><p>same</p></body></html>",
        screenshot_variant="plain",
        entities=[],
    )
    destination = tmp_path / "comparison.json"
    document = compare_cases(left, right)
    write_comparison(document, destination)

    with pytest.raises(FileExistsError):
        write_comparison(document, destination)
