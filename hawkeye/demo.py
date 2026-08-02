"""Create a deterministic, sanitized local case corpus for the Gemastik judge walkthrough."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

from hawkeye.comparison import compare_cases, write_comparison
from hawkeye.diagnostics.models import (
    DiagnosticEvidenceReference,
    RenderCheckpointMeasurement,
    RenderDiagnosticsDocument,
)
from hawkeye.graph import build_graph
from hawkeye.models import (
    CandidateCorpusSnapshot,
    CandidateDocument,
    CandidateEvidenceReference,
    CandidateObservation,
    CandidateReason,
    CandidateRecord,
    CaptureOutcome,
    CaseRecord,
    CrawlConfiguration,
    CrawlPageRecord,
    EvidenceRecord,
    ExtractedEntity,
)
from hawkeye.review_app.loader import CaseLoader

_NOW = datetime(2026, 8, 2, tzinfo=UTC)
_EMPTY_MANIFEST_SHA256 = hashlib.sha256(b"").hexdigest()


@dataclass(frozen=True)
class DemoResult:
    """Paths written by the deterministic demo builder; all are new local files."""

    output_directory: Path
    cases_directory: Path
    comparisons_directory: Path
    case_ids: list[str]
    comparison_path: Path


def build_demo(output_directory: Path | str) -> DemoResult:
    """Write a new offline demo corpus without collecting, fetching, or overwriting anything."""

    output = Path(output_directory).expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing demo output: {output}")
    cases_directory = output / "cases"
    comparisons_directory = output / "comparisons"
    cases_directory.mkdir(parents=True)
    comparisons_directory.mkdir()

    harbor = _write_demo_case(
        cases_directory,
        case_id="demo-harbor",
        hostname="harbor.demo.invalid",
        title="Harbor evidence record",
        entity_suffix="harbor",
        usable=True,
    )
    tide = _write_demo_case(
        cases_directory,
        case_id="demo-tide",
        hostname="tide.demo.invalid",
        title="Tide evidence record",
        entity_suffix="tide",
        usable=True,
    )
    _write_demo_case(
        cases_directory,
        case_id="demo-restricted",
        hostname="restricted.demo.invalid",
        title="Restricted capture record",
        entity_suffix="restricted",
        usable=False,
    )
    _write_diagnostic(cases_directory, "demo-harbor")
    comparison_path = write_comparison(
        compare_cases(harbor, tide), comparisons_directory / "demo-harbor--demo-tide.json"
    )
    return DemoResult(
        output_directory=output,
        cases_directory=cases_directory,
        comparisons_directory=comparisons_directory,
        case_ids=["demo-harbor", "demo-restricted", "demo-tide"],
        comparison_path=comparison_path,
    )


def _write_demo_case(
    root: Path,
    *,
    case_id: str,
    hostname: str,
    title: str,
    entity_suffix: str,
    usable: bool,
) -> Path:
    directory = root / case_id
    directory.mkdir()
    (directory / "pages").mkdir()
    (directory / "screenshots").mkdir()
    final_url = f"https://{hostname}/record?session=demo-token&view=local"
    html = _demo_html(title, hostname, usable).encode("utf-8")
    screenshot = _demo_screenshot(case_id, usable)
    html_path = directory / "pages" / "page-001.html"
    screenshot_path = directory / "screenshots" / "page-001.png"
    html_path.write_bytes(html)
    screenshot_path.write_bytes(screenshot)

    html_evidence = EvidenceRecord(
        id="evidence-page-001",
        type="html_page",
        source_url=final_url,
        path="pages/page-001.html",
        collected_at=_NOW,
        sha256=hashlib.sha256(html).hexdigest(),
        page_id="page-001",
    )
    screenshot_evidence = EvidenceRecord(
        id="evidence-screenshot-001",
        type="screenshot",
        source_url=final_url,
        path="screenshots/page-001.png",
        collected_at=_NOW,
        sha256=hashlib.sha256(screenshot).hexdigest(),
        page_id="page-001",
        viewport={"width": 960, "height": 540},
        image_dimensions={"width": 960, "height": 540},
    )
    outcome = CaptureOutcome.CONTENT if usable else CaptureOutcome.CONSENT_WALL
    case = CaseRecord(
        case_id=case_id,
        seed_url=f"https://{hostname}/",
        final_url=final_url,
        status="completed",
        started_at=_NOW,
        completed_at=_NOW,
        navigation_status="captured",
        capture_outcome=outcome,
        content_usable=usable,
        classification_reasons=[] if usable else ["fixture consent-wall classification"],
        page_title=title,
        page_count=1,
        candidate_count=1 if usable else 0,
        crawl_configuration=_crawl_configuration(hostname),
        allowed_crawl_hosts=[hostname],
        total_request_count=2,
        total_declared_response_bytes=len(html) + len(screenshot),
    )
    page = CrawlPageRecord(
        id="page-001",
        url=case.seed_url,
        normalized_url=case.seed_url,
        depth=0,
        state="completed",
        final_url=final_url,
        navigation_status="captured",
        capture_outcome=outcome,
        content_usable=usable,
        classification_reasons=case.classification_reasons,
        page_title=title,
        html_evidence_id=html_evidence.id,
        screenshot_evidence_id=screenshot_evidence.id,
        content_sha256=html_evidence.sha256,
        content_type="text/html",
    )
    entities = _entities(case_id, final_url, html_evidence.id, entity_suffix) if usable else []
    graph = build_graph(
        case=case,
        pages=[page],
        evidence=[html_evidence, screenshot_evidence],
        entities=entities,
    )
    payloads: dict[str, object] = {
        "case.json": case.model_dump(mode="json"),
        "pages.json": [page.model_dump(mode="json")],
        "evidence.json": [
            html_evidence.model_dump(mode="json"),
            screenshot_evidence.model_dump(mode="json"),
        ],
        "entities.json": [entity.model_dump(mode="json") for entity in entities],
        "graph.json": graph.model_dump(mode="json"),
    }
    if usable:
        candidates, observations = _candidate_documents(case, html_evidence)
        payloads["candidates.json"] = candidates.model_dump(mode="json")
        payloads["candidate_observations.json"] = [
            observation.model_dump(mode="json") for observation in observations
        ]
    for filename, payload in payloads.items():
        (directory / filename).write_text(
            f"{json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)}\n",
            encoding="utf-8",
        )
    return directory


def _crawl_configuration(hostname: str) -> CrawlConfiguration:
    return CrawlConfiguration(
        max_depth=1,
        max_pages_total=5,
        max_redirects_per_page=5,
        page_timeout_seconds=30,
        case_timeout_seconds=120,
        max_html_bytes=2_000_000,
        max_total_requests=200,
        max_declared_response_bytes=10_000_000,
        allowed_crawl_hosts=[hostname],
    )


def _entities(
    case_id: str, source_url: str, evidence_id: str, entity_suffix: str
) -> list[ExtractedEntity]:
    return [
        ExtractedEntity(
            id="entity-telegram-001",
            type="telegram",
            value="@fixture_signal",
            normalized_value="@fixture_signal",
            source_evidence_id=evidence_id,
            source_url=source_url,
            extraction_method="demo_fixture",
            confidence=1.0,
        ),
        ExtractedEntity(
            id="entity-referral-001",
            type="referral",
            value="ref=fixture-shared",
            normalized_value="ref=fixture-shared",
            source_evidence_id=evidence_id,
            source_url=source_url,
            extraction_method="demo_fixture",
            confidence=1.0,
        ),
        ExtractedEntity(
            id="entity-asset-001",
            type="external_asset_url",
            value=f"https://assets.demo.invalid/{entity_suffix}/bundle.js",
            normalized_value=f"https://assets.demo.invalid/{entity_suffix}/bundle.js",
            source_evidence_id=evidence_id,
            source_url=source_url,
            extraction_method="demo_fixture",
            confidence=1.0,
        ),
    ]


def _candidate_documents(
    case: CaseRecord, evidence: EvidenceRecord
) -> tuple[CandidateDocument, list[CandidateObservation]]:
    observation = CandidateObservation(
        id="candidate-observation-001",
        observation_type="external_link",
        source_case_id=case.case_id,
        source_evidence_id=evidence.id,
        source_url=case.final_url or case.seed_url,
        target_url="https://pending.demo.invalid/",
        target_host="pending.demo.invalid",
        direction="source_to_candidate",
        discovery_method="html_anchor",
        candidate_decision="accepted",
    )
    candidate = CandidateRecord(
        candidate_id="candidate-host:pending.demo.invalid",
        hostname="pending.demo.invalid",
        registrable_domain="demo.invalid",
        suffix_type="private",
        scope_relation="different_registrable_domain",
        observed_hosts=["pending.demo.invalid"],
        discovery_priority_score=10,
        reasons=[
            CandidateReason(
                reason_type="external_link",
                signal_value="pending.demo.invalid",
                weight=10,
                signal_quality="observed",
                corpus_frequency=0,
                corpus_case_count=0,
                corpus_domain_count=0,
                source_case_ids=[case.case_id],
                source_urls=[case.final_url or case.seed_url],
                supporting_evidence_ids=[evidence.id],
                supporting_evidence_refs=[
                    CandidateEvidenceReference(
                        case_id=case.case_id,
                        evidence_id=evidence.id,
                        observation_id=observation.id,
                    )
                ],
                source_observation_ids=[observation.id],
                direction="source_to_candidate",
                discovery_method="html_anchor",
            )
        ],
    )
    document = CandidateDocument(
        source_case_id=case.case_id,
        candidates=[candidate],
        excluded_observation_count=0,
        corpus=CandidateCorpusSnapshot(
            case_ids=[],
            case_count=0,
            manifest_sha256=_EMPTY_MANIFEST_SHA256,
            generated_at=_NOW,
        ),
    )
    return document, [observation]


def _write_diagnostic(cases_directory: Path, case_id: str) -> None:
    """Attach a stable noncanonical diagnostic with verified canonical references."""

    loaded = CaseLoader(cases_directory).load(case_id)
    html = loaded.evidence_by_id["evidence-page-001"]
    screenshot = loaded.evidence_by_id["evidence-screenshot-001"]
    checkpoint = RenderCheckpointMeasurement(
        elapsed_ms=0,
        document_ready_state="complete",
        html_bytes=1200,
        visible_text_chars=180,
        element_count=16,
        anchor_count=1,
        image_count=0,
        iframe_count=0,
        canvas_count=0,
        document_height=540,
        screenshot_sha256="0" * 64,
        screenshot_bytes=512,
        screenshot_entropy=1.0,
    )
    document = RenderDiagnosticsDocument(
        generated_at=_NOW,
        engine_version="demo-fixture",
        command="hawkeye demo",
        collection_mode="fixture",
        source_case_id=case_id,
        source_case_manifest_sha256=loaded.manifest_sha256,
        source_page_id="page-001",
        source_url=loaded.case.final_url or loaded.case.seed_url,
        source_evidence_refs=[
            DiagnosticEvidenceReference(evidence_id=html.id, type="html_page", sha256=html.sha256),
            DiagnosticEvidenceReference(
                evidence_id=screenshot.id,
                type="screenshot",
                sha256=screenshot.sha256,
            ),
        ],
        checkpoint_schedule_ms=[0, 500, 1500, 3000],
        total_diagnostic_time_ms=3000,
        status="stable_across_checkpoints",
        checkpoints=[checkpoint],
    )
    directory = cases_directory / case_id / "diagnostics"
    directory.mkdir()
    (directory / "render-diagnostics.json").write_text(
        f"{document.model_dump_json(indent=2)}\n", encoding="utf-8"
    )


def _demo_html(title: str, hostname: str, usable: bool) -> str:
    if not usable:
        return (
            '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f"<title>{title}</title></head><body><main><h1>{title}</h1>"
            "<p>Fixture restriction record. No target-content entities are claimed.</p>"
            "</main></body></html>"
        )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{title}</title></head><body><main><h1>{title}</h1>"
        f"<p>Sanitized local evidence fixture for {hostname}.</p>"
        "<p>Observed marker: @fixture_signal and ref=fixture-shared.</p>"
        '<a href="https://pending.demo.invalid/">Fixture pending lead</a>'
        "</main></body></html>"
    )


def _demo_screenshot(case_id: str, usable: bool) -> bytes:
    """Create a small deterministic illustration without copied branding or remote assets."""

    background = (28, 49, 43) if usable else (88, 58, 46)
    accent = (208, 181, 107) if usable else (232, 190, 164)
    image = Image.new("RGB", (960, 540), color=background)
    draw = ImageDraw.Draw(image)
    draw.rectangle((54, 54, 906, 486), outline=accent, width=4)
    draw.line((96, 158, 864, 158), fill=accent, width=3)
    draw.line((96, 250, 720, 250), fill=accent, width=2)
    draw.line((96, 304, 790, 304), fill=accent, width=2)
    draw.line((96, 358, 630, 358), fill=accent, width=2)
    draw.text((96, 96), case_id, fill=accent)
    draw.text((96, 420), "LOCAL FIXTURE · HUMAN REVIEW REQUIRED", fill=accent)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
