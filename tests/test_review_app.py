"""V1 local investigator-console tests: verified-only evidence, no path API, no remote UI loads."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

from hawkeye.comparison import compare_cases, write_comparison
from hawkeye.diagnostics.models import (
    DiagnosticEvidenceReference,
    RenderCheckpointMeasurement,
    RenderDiagnosticsDocument,
)
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
    GraphDocument,
    GraphEdge,
    GraphNode,
)
from hawkeye.review_app import create_app
from hawkeye.review_app.loader import CaseLoader, CaseNotFoundError, safe_display_url
from hawkeye.review_app.server import run_local_server

NOW = datetime(2026, 8, 2, tzinfo=UTC)


def _write_case(root: Path, *, case_id: str = "review-case") -> Path:
    directory = root / case_id
    (directory / "pages").mkdir(parents=True)
    (directory / "screenshots").mkdir()
    html = b"""<!doctype html><html><body><script>window.bad = true</script>
    <img src='https://attacker.example/track.png'><p>Captured evidence only.</p></body></html>"""
    image = Image.new("RGB", (8, 8), color=(20, 80, 50))
    image_output = BytesIO()
    image.save(image_output, format="PNG")
    screenshot = image_output.getvalue()
    html_path = directory / "pages" / "page-001.html"
    screenshot_path = directory / "screenshots" / "page-001.png"
    html_path.write_bytes(html)
    screenshot_path.write_bytes(screenshot)
    html_evidence = EvidenceRecord(
        id="evidence-page-001",
        type="html_page",
        source_url="https://review.example/?token=top-secret&safe=visible",
        path="pages/page-001.html",
        collected_at=NOW,
        sha256=hashlib.sha256(html).hexdigest(),
        page_id="page-001",
    )
    screenshot_evidence = EvidenceRecord(
        id="evidence-screenshot-001",
        type="screenshot",
        source_url="https://review.example/",
        path="screenshots/page-001.png",
        collected_at=NOW,
        sha256=hashlib.sha256(screenshot).hexdigest(),
        page_id="page-001",
        viewport={"width": 8, "height": 8},
        image_dimensions={"width": 8, "height": 8},
    )
    case = CaseRecord(
        case_id=case_id,
        seed_url="https://review.example/",
        final_url="https://review.example/?token=top-secret&safe=visible",
        status="completed",
        started_at=NOW,
        completed_at=NOW,
        navigation_status="captured",
        capture_outcome=CaptureOutcome.CONTENT,
        content_usable=True,
        page_count=1,
        candidate_count=1,
        crawl_configuration=CrawlConfiguration(
            max_depth=1,
            max_pages_total=5,
            max_redirects_per_page=5,
            page_timeout_seconds=30,
            case_timeout_seconds=120,
            max_html_bytes=2_000_000,
            max_total_requests=200,
            max_declared_response_bytes=10_000_000,
            allowed_crawl_hosts=["review.example"],
        ),
    )
    page = CrawlPageRecord(
        id="page-001",
        url=case.seed_url,
        normalized_url=case.seed_url,
        depth=0,
        state="completed",
        final_url=case.final_url,
        navigation_status="captured",
        capture_outcome=CaptureOutcome.CONTENT,
        content_usable=True,
        html_evidence_id=html_evidence.id,
        screenshot_evidence_id=screenshot_evidence.id,
        content_sha256=html_evidence.sha256,
    )
    entity = ExtractedEntity(
        id="entity-001",
        type="external_link",
        value="https://user:password@candidate.example/path?token=leak&safe=value",
        normalized_value="https://user:password@candidate.example/path?token=leak&safe=value",
        source_evidence_id=html_evidence.id,
        source_url=case.final_url,
        extraction_method="fixture",
        confidence=1.0,
    )
    observation = CandidateObservation(
        id="candidate-observation-001",
        observation_type="external_link",
        source_case_id=case_id,
        source_evidence_id=html_evidence.id,
        source_url=case.final_url,
        target_url="https://candidate.example/",
        target_host="candidate.example",
        direction="source_to_candidate",
        discovery_method="html_anchor",
        candidate_decision="accepted",
    )
    candidate = CandidateRecord(
        candidate_id="candidate-host:candidate.example",
        hostname="candidate.example",
        registrable_domain="candidate.example",
        suffix_type="icann",
        scope_relation="different_registrable_domain",
        observed_hosts=["candidate.example"],
        discovery_priority_score=10,
        reasons=[
            CandidateReason(
                reason_type="external_link",
                weight=10,
                signal_quality="observed",
                corpus_frequency=0,
                corpus_case_count=0,
                corpus_domain_count=0,
                source_case_ids=[case_id],
                source_urls=[case.final_url],
                supporting_evidence_ids=[html_evidence.id],
                supporting_evidence_refs=[
                    CandidateEvidenceReference(
                        case_id=case_id,
                        evidence_id=html_evidence.id,
                        observation_id=observation.id,
                    )
                ],
                source_observation_ids=[observation.id],
                direction="source_to_candidate",
                discovery_method="html_anchor",
            )
        ],
    )
    candidates = CandidateDocument(
        source_case_id=case_id,
        candidates=[candidate],
        excluded_observation_count=0,
        corpus=CandidateCorpusSnapshot(
            case_ids=[],
            case_count=0,
            manifest_sha256=hashlib.sha256(b"").hexdigest(),
            generated_at=NOW,
        ),
    )
    graph = GraphDocument(
        nodes=[
            GraphNode(id=f"case:{case_id}", type="case", label=case_id),
            GraphNode(id="domain:review.example", type="domain", label="review.example"),
            GraphNode(id="page:page-001", type="page", label="review.example /"),
            GraphNode(id="domain:candidate.example", type="domain", label="candidate.example"),
        ],
        edges=[
            GraphEdge(
                id="edge-started-from",
                source=f"case:{case_id}",
                target="domain:review.example",
                type="started_from",
            ),
            GraphEdge(
                id="edge-contains-page",
                source="domain:review.example",
                target="page:page-001",
                type="contains_page",
            ),
            GraphEdge(
                id="edge-links-to",
                source="page:page-001",
                target="domain:candidate.example",
                type="links_to",
                evidence_id=html_evidence.id,
                source_url=case.final_url,
                extraction_method="fixture",
                confidence=1.0,
            ),
        ],
        metadata={"schema_version": "fixture-graph-1"},
    )
    payloads = {
        "case.json": case.model_dump(mode="json"),
        "pages.json": [page.model_dump(mode="json")],
        "evidence.json": [
            html_evidence.model_dump(mode="json"),
            screenshot_evidence.model_dump(mode="json"),
        ],
        "entities.json": [entity.model_dump(mode="json")],
        "candidates.json": candidates.model_dump(mode="json"),
        "candidate_observations.json": [observation.model_dump(mode="json")],
        "graph.json": graph.model_dump(mode="json"),
    }
    for filename, payload in payloads.items():
        (directory / filename).write_text(
            f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8"
        )
    return directory


def _write_diagnostic(root: Path, case_id: str) -> None:
    """Attach a valid, deliberately noncanonical G1 diagnostic to a fixture case."""

    loaded = CaseLoader(root).load(case_id)
    html = loaded.evidence_by_id["evidence-page-001"]
    screenshot = loaded.evidence_by_id["evidence-screenshot-001"]
    checkpoint = RenderCheckpointMeasurement(
        elapsed_ms=0,
        document_ready_state="complete",
        html_bytes=100,
        visible_text_chars=20,
        element_count=4,
        anchor_count=0,
        image_count=0,
        iframe_count=0,
        canvas_count=0,
        document_height=100,
        screenshot_sha256="0" * 64,
        screenshot_bytes=64,
        screenshot_entropy=1.0,
    )
    diagnostic = RenderDiagnosticsDocument(
        generated_at=NOW,
        engine_version="fixture",
        command="fixture",
        collection_mode="fixture",
        source_case_id=case_id,
        source_case_manifest_sha256=loaded.manifest_sha256,
        source_page_id="page-001",
        source_url=loaded.case.final_url or loaded.case.seed_url,
        source_evidence_refs=[
            DiagnosticEvidenceReference(
                evidence_id=html.id,
                type=html.type,
                sha256=html.sha256,
            ),
            DiagnosticEvidenceReference(
                evidence_id=screenshot.id,
                type=screenshot.type,
                sha256=screenshot.sha256,
            ),
        ],
        checkpoint_schedule_ms=[0, 500, 1500, 3000],
        total_diagnostic_time_ms=3000,
        status="continued_changing_at_budget_end",
        checkpoints=[checkpoint],
    )
    destination = root / case_id / "diagnostics"
    destination.mkdir()
    (destination / "render-diagnostics.json").write_text(
        f"{diagnostic.model_dump_json(indent=2)}\n", encoding="utf-8"
    )


class _Client:
    """Use HTTPX's ASGI transport directly so V1 tests do not depend on TestClient shims."""

    def __init__(self, root: Path, comparisons_root: Path | None = None) -> None:
        self._app = create_app(root, comparisons_root=comparisons_root)

    def get(self, path: str, *, headers: dict[str, str] | None = None) -> httpx.Response:
        async def request() -> httpx.Response:
            transport = httpx.ASGITransport(app=self._app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://127.0.0.1"
            ) as client:
                return await client.get(path, headers=headers)

        return asyncio.run(request())


def _client(root: Path, comparisons_root: Path | None = None) -> _Client:
    return _Client(root, comparisons_root)


def test_read_only_api_uses_verified_ids_redacts_display_values_and_sets_csp(
    tmp_path: Path,
) -> None:
    root = tmp_path / "cases"
    _write_case(root)
    client = _client(root)

    index = client.get("/")
    listing = client.get("/api/cases")
    detail = client.get("/api/cases/review-case")

    assert index.status_code == 200
    assert "default-src 'self'" in index.headers["content-security-policy"]
    assert "https://" not in index.text
    assert "access-control-allow-origin" not in index.headers
    chunk_match = re.search(r'href="/assets/(chunks/[^"]+\.js)"', index.text)
    assert chunk_match is not None
    chunk = client.get(f"/assets/{chunk_match.group(1)}")
    assert chunk.status_code == 200
    assert chunk.headers["content-type"].startswith("text/javascript")
    brand_image = client.get("/assets/hawkeye-avatar.png")
    assert brand_image.status_code == 200
    assert brand_image.headers["content-type"] == "image/png"
    favicon = client.get("/assets/favicon.ico")
    manifest = client.get("/assets/site.webmanifest")
    social_card = client.get("/assets/og-image-1200x630.png")
    assert favicon.status_code == 200
    assert favicon.headers["content-type"] == "image/x-icon"
    assert manifest.status_code == 200
    assert manifest.headers["content-type"] == "application/manifest+json"
    assert manifest.json()["short_name"] == "HAWK-EYE"
    assert social_card.status_code == 200
    assert social_card.headers["content-type"] == "image/png"
    font_match = re.search(
        r"url\(/assets/([^)]*\.(?:woff2))\)", client.get("/assets/styles.css").text
    )
    assert font_match is not None
    font = client.get(f"/assets/{font_match.group(1)}")
    assert font.status_code == 200
    assert font.headers["content-type"] == "font/woff2"
    assert client.get("/assets/chunks/%2e%2e%2fapp.js").status_code == 404
    assert client.get("/assets/not-an-approved-file.png").status_code == 404
    assert listing.json()["cases"][0]["integrity"] == "verified"
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["final_url_display"] == "https://review.example/?token=[redacted]&safe=visible"
    assert "value" not in payload["entities"][0]
    assert "password" not in payload["entities"][0]["display_value"]
    assert "leak" not in payload["entities"][0]["display_value"]
    assert payload["candidates"][0]["relationship"] is None
    assert "C:\\" not in json.dumps(payload)
    assert safe_display_url("http://review.example:443/path") == "http://review.example:443/path"
    assert safe_display_url("https://review.example:80/path") == "https://review.example:80/path"


def test_html_artifact_is_an_attachment_not_renderable_html_and_screenshot_is_local(
    tmp_path: Path,
) -> None:
    root = tmp_path / "cases"
    _write_case(root)
    client = _client(root)

    html = client.get("/api/cases/review-case/artifacts/evidence-page-001")
    screenshot = client.get("/api/cases/review-case/artifacts/evidence-screenshot-001")

    assert html.status_code == 200
    assert html.headers["content-type"].startswith("text/plain")
    assert html.headers["content-disposition"].startswith("attachment")
    assert b"window.bad" in html.content
    content_security_policy = html.headers["content-security-policy"]
    assert "img-src 'self' data:" in content_security_policy
    assert "script-src 'self';" in content_security_policy
    assert (
        "'unsafe-inline'" not in content_security_policy.split("script-src", 1)[1].split(";", 1)[0]
    )
    assert "style-src 'self' 'unsafe-inline';" in content_security_policy
    assert screenshot.status_code == 200
    assert screenshot.headers["content-type"] == "image/png"
    assert screenshot.headers["content-disposition"].startswith("inline")


def test_loopback_host_validation_blocks_dns_rebinding_headers(tmp_path: Path) -> None:
    root = tmp_path / "cases"
    _write_case(root)
    client = _client(root)

    assert client.get("/health", headers={"host": "127.0.0.1:8760"}).status_code == 200
    assert client.get("/health", headers={"host": "localhost:8760"}).status_code == 200

    blocked = client.get(
        "/health",
        headers={
            "host": "evil.example",
            "forwarded": "host=127.0.0.1",
            "x-forwarded-host": "127.0.0.1",
        },
    )
    assert blocked.status_code == 400
    assert "default-src 'self'" in blocked.headers["content-security-policy"]
    assert client.get("/health", headers={"host": "192.168.1.10"}).status_code == 400
    assert client.get("/health", headers={"host": "0.0.0.0"}).status_code == 400
    assert (
        client.get(
            "/health",
            headers={"host": "127.0.0.1", "x-forwarded-host": "evil.example"},
        ).status_code
        == 200
    )


def test_tampered_artifact_or_unsafe_evidence_path_returns_integrity_error(tmp_path: Path) -> None:
    root = tmp_path / "cases"
    case_directory = _write_case(root)
    client = _client(root)
    (case_directory / "pages" / "page-001.html").write_text("tampered", encoding="utf-8")

    response = client.get("/api/cases/review-case")

    assert response.status_code == 409
    assert response.json() == {"error": "case_integrity_error"}

    unsafe_root = tmp_path / "unsafe-cases"
    unsafe_case = _write_case(unsafe_root)
    evidence = json.loads((unsafe_case / "evidence.json").read_text(encoding="utf-8"))
    evidence[0]["path"] = "../outside.html"
    (unsafe_case / "evidence.json").write_text(
        f"{json.dumps(evidence, indent=2, sort_keys=True)}\n", encoding="utf-8"
    )
    unsafe_client = _client(unsafe_root)

    unsafe_response = unsafe_client.get("/api/cases/review-case")

    assert unsafe_response.status_code == 409
    assert unsafe_response.json() == {"error": "case_integrity_error"}

    malformed_root = tmp_path / "malformed-cases"
    malformed_case = _write_case(malformed_root)
    malformed_screenshot = malformed_case / "screenshots" / "page-001.png"
    malformed_screenshot.write_bytes(b"not a png")
    malformed_evidence = json.loads((malformed_case / "evidence.json").read_text(encoding="utf-8"))
    malformed_evidence[1]["sha256"] = hashlib.sha256(b"not a png").hexdigest()
    (malformed_case / "evidence.json").write_text(
        f"{json.dumps(malformed_evidence, indent=2, sort_keys=True)}\n", encoding="utf-8"
    )
    malformed_client = _client(malformed_root)

    malformed_response = malformed_client.get("/api/cases/review-case")

    assert malformed_response.status_code == 409
    assert malformed_response.json() == {"error": "case_integrity_error"}


def test_loader_rejects_nonopaque_case_ids_and_unknown_evidence_ids(tmp_path: Path) -> None:
    root = tmp_path / "cases"
    _write_case(root)
    loader = CaseLoader(root)
    client = _client(root)

    with pytest.raises(CaseNotFoundError):
        loader.load("..")
    assert client.get("/api/cases/review-case/artifacts/missing-evidence").status_code == 404


def test_case_detail_exposes_traceable_graph_leads_and_noncanonical_diagnostics(
    tmp_path: Path,
) -> None:
    root = tmp_path / "cases"
    _write_case(root)
    _write_diagnostic(root, "review-case")
    payload = _client(root).get("/api/cases/review-case").json()

    assert payload["seed_url_display"] == "https://review.example/"
    assert payload["collection_limits"] == {
        "max_depth": 1,
        "max_pages_total": 5,
        "max_redirects_per_page": 5,
        "page_timeout_seconds": 30.0,
        "case_timeout_seconds": 120.0,
    }
    assert payload["entities"][0]["source_evidence_id"] == "evidence-page-001"
    assert payload["candidates"][0]["status"] == "pending"
    assert payload["candidates"][0]["relationship"] is None
    reason_ref = payload["candidates"][0]["reasons"][0]["evidence_refs"][0]
    assert reason_ref == {
        "case_id": "review-case",
        "evidence_id": "evidence-page-001",
        "observation_id": "candidate-observation-001",
        "available": True,
    }
    assert payload["graph"]["edge_count"] == 3
    observed_edge = next(
        edge for edge in payload["graph"]["edges"] if edge["id"] == "edge-links-to"
    )
    assert observed_edge["relationship_status"] == "observed_evidence"
    assert observed_edge["evidence"]["evidence_id"] == "evidence-page-001"
    assert payload["diagnostic"] == {
        "status": "continued_changing_at_budget_end",
        "collection_mode": "fixture",
        "source_page_id": "page-001",
        "checkpoint_count": 1,
        "diagnostic_wait_budget_ms": 3000,
        "evidence_refs": [
            {
                "case_id": "review-case",
                "evidence_id": "evidence-page-001",
                "observation_id": None,
                "available": True,
            },
            {
                "case_id": "review-case",
                "evidence_id": "evidence-screenshot-001",
                "observation_id": None,
                "available": True,
            },
        ],
    }
    assert payload["diagnostic_integrity_warning"] is None


def test_unusable_case_and_corrupt_diagnostic_are_visible_as_limits_not_silent_facts(
    tmp_path: Path,
) -> None:
    root = tmp_path / "cases"
    case_directory = _write_case(root)
    case = json.loads((case_directory / "case.json").read_text(encoding="utf-8"))
    case.update(
        {
            "capture_outcome": "bot_challenge",
            "content_usable": False,
            "candidate_count": 0,
            "classification_reasons": ["fixture restriction message"],
        }
    )
    (case_directory / "case.json").write_text(
        f"{json.dumps(case, indent=2, sort_keys=True)}\n", encoding="utf-8"
    )
    page = json.loads((case_directory / "pages.json").read_text(encoding="utf-8"))
    page[0].update(
        {
            "capture_outcome": "bot_challenge",
            "content_usable": False,
            "classification_reasons": ["fixture restriction message"],
        }
    )
    (case_directory / "pages.json").write_text(
        f"{json.dumps(page, indent=2, sort_keys=True)}\n", encoding="utf-8"
    )
    (case_directory / "entities.json").write_text("[]\n", encoding="utf-8")
    (case_directory / "candidates.json").unlink()
    (case_directory / "candidate_observations.json").unlink()
    diagnostic_directory = case_directory / "diagnostics"
    diagnostic_directory.mkdir()
    (diagnostic_directory / "render-diagnostics.json").write_text("{invalid", encoding="utf-8")

    response = _client(root).get("/api/cases/review-case")

    assert response.status_code == 200
    payload = response.json()
    assert payload["content_usable"] is False
    assert payload["capture_outcome"] == "bot_challenge"
    assert payload["entities"] == []
    assert payload["candidates"] == []
    assert payload["diagnostic"] is None
    assert "cannot be verified" in payload["diagnostic_integrity_warning"]


def test_verified_comparison_projection_and_invalid_companion_warning(tmp_path: Path) -> None:
    root = tmp_path / "cases"
    left = _write_case(root, case_id="left-case")
    right = _write_case(root, case_id="right-case")
    comparison_root = tmp_path / "comparisons"
    comparison_root.mkdir()
    comparison = compare_cases(left, right)
    write_comparison(comparison, comparison_root / "left-right.json")
    (comparison_root / "corrupt.json").write_text("{invalid", encoding="utf-8")

    response = _client(root, comparison_root).get("/api/cases/left-case")

    assert response.status_code == 200
    payload = response.json()
    assert payload["comparison_integrity_warning"] is True
    assert len(payload["comparisons"]) == 1
    displayed = payload["comparisons"][0]
    assert displayed["review_status"] == "needs_review"
    assert displayed["scoring_policy_version"] == "v0.3-offline-comparison-1"
    assert displayed["components"]
    assert all(
        reference["available"]
        for component in displayed["components"]
        for reference in component["evidence_refs"]
    )


def test_hostile_display_values_are_bounded_inert_text_inputs(tmp_path: Path) -> None:
    root = tmp_path / "cases"
    case_directory = _write_case(root)
    candidates = json.loads((case_directory / "candidates.json").read_text(encoding="utf-8"))
    candidates["candidates"][0]["hostname"] = "<script>window.pwned=1</script>" + "x" * 300
    candidates["candidates"][0]["registrable_domain"] = "xn--bcher-kva.example"
    (case_directory / "candidates.json").write_text(
        f"{json.dumps(candidates, indent=2, sort_keys=True)}\n", encoding="utf-8"
    )
    entities = json.loads((case_directory / "entities.json").read_text(encoding="utf-8"))
    entities[0].update(
        {
            "type": "telegram",
            "value": "\u0000'=SUM(1,1) <img src=x onerror=alert(1)>",
            "normalized_value": "\u0000'=SUM(1,1) <img src=x onerror=alert(1)>",
        }
    )
    (case_directory / "entities.json").write_text(
        f"{json.dumps(entities, indent=2, sort_keys=True)}\n", encoding="utf-8"
    )

    payload = _client(root).get("/api/cases/review-case").json()

    assert payload["candidates"][0]["hostname"].endswith("…")
    assert len(payload["candidates"][0]["hostname"]) == 256
    assert "\x00" not in payload["entities"][0]["display_value"]
    assert payload["entities"][0]["display_value"].startswith("'=SUM")


def test_react_ui_build_preserves_local_evidence_safety_and_accessibility() -> None:
    repository_root = Path(__file__).parents[1]
    static_root = repository_root / "apps" / "api" / "src" / "hawkeye" / "review_app" / "static"
    frontend_root = repository_root / "apps" / "web" / "src"
    script = (static_root / "app.js").read_text(encoding="utf-8")
    html = (static_root / "index.html").read_text(encoding="utf-8")
    styles = (static_root / "styles.css").read_text(encoding="utf-8")
    chunks = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted((static_root / "chunks").glob("*.js"))
    )
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(frontend_root.rglob("*.tsx"))
    )

    # React may use innerHTML internally; application code must not opt into raw HTML injection.
    assert "dangerouslySetInnerHTML" not in source
    assert "window.open" not in source
    assert 'target="_blank"' not in source
    assert "<iframe" not in source
    assert 'id="root"' in html
    assert 'src="/assets/app.js"' in html
    assert 'href="/assets/styles.css"' in html
    assert 'href="/assets/favicon.ico"' in html
    assert 'href="/assets/site.webmanifest"' in html
    assert 'content="/assets/og-image-1200x630.png"' in html
    assert 'content="1200"' in html
    assert 'content="630"' in html
    assert 'content="noindex, nofollow, noarchive, nosnippet"' in html
    assert "http://" not in html
    assert "https://" not in html
    assert "/api/investigation-jobs" in script + chunks
    assert "Relationship: not determined" in chunks
    assert "aria-current" in chunks
    assert 'screenshots.find((item) => item.label === "Full page")' in source
    assert 'aria-label="Timeline position"' in source
    assert 'defaultValue="overview"' in source
    assert "workspace-left-collapsed" in source
    assert 'language === "id"' in source
    assert "Evidence package verified" not in source
    assert ".scan-radar" in styles
    assert ".workspace-grid" in styles
    assert ".graph-canvas" in styles
    assert ".graph-lens-control" in styles
    assert ".quick-evidence-group" in styles
    assert ".evidence-card-detail>img" in styles
    assert "width<=1120px" in styles
    assert "prefers-reduced-motion" in styles
    assert ":focus-visible" in styles


def test_server_runner_is_hard_bound_to_loopback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "cases"
    _write_case(root)
    observed: dict[str, object] = {}

    def fake_run(app: object, **kwargs: object) -> None:
        observed["app"] = app
        observed.update(kwargs)

    monkeypatch.setattr("hawkeye.review_app.server.uvicorn.run", fake_run)

    run_local_server(root, port=8761)

    assert observed["host"] == "127.0.0.1"
    assert observed["port"] == 8761
    assert observed["proxy_headers"] is False
    assert observed["access_log"] is False
