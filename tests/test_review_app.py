"""V1 local investigator-console tests: verified-only evidence, no path API, no remote UI loads."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

from hawkeye.models import (
    CandidateCorpusSnapshot,
    CandidateDocument,
    CandidateEvidenceReference,
    CandidateObservation,
    CandidateReason,
    CandidateRecord,
    CaptureOutcome,
    CaseRecord,
    CrawlPageRecord,
    EvidenceRecord,
    ExtractedEntity,
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
    }
    for filename, payload in payloads.items():
        (directory / filename).write_text(
            f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8"
        )
    return directory


class _Client:
    """Use HTTPX's ASGI transport directly so V1 tests do not depend on TestClient shims."""

    def __init__(self, root: Path) -> None:
        self._app = create_app(root)

    def get(self, path: str, *, headers: dict[str, str] | None = None) -> httpx.Response:
        async def request() -> httpx.Response:
            transport = httpx.ASGITransport(app=self._app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://127.0.0.1"
            ) as client:
                return await client.get(path, headers=headers)

        return asyncio.run(request())


def _client(root: Path) -> _Client:
    return _Client(root)


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
    assert "img-src 'self' data:" in html.headers["content-security-policy"]
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


def test_ui_assets_do_not_use_html_injection_or_external_navigation() -> None:
    static_root = Path(__file__).parents[1] / "hawkeye" / "review_app" / "static"
    script = (static_root / "app.js").read_text(encoding="utf-8")
    html = (static_root / "index.html").read_text(encoding="utf-8")

    assert "innerHTML" not in script
    assert "window.open" not in script
    assert "http://" not in script + html
    assert "https://" not in script + html


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
