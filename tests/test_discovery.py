"""V0.4 external-discovery tests using saved source responses only."""

from __future__ import annotations

import hashlib
import json
import socket
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from hawkeye.collector.safety import SafetyPolicy
from hawkeye.discovery import (
    ExternalDiscoveryInputError,
    ExternalDiscoverySourceError,
    UrlscanPublicSearchSource,
    discover_case,
    urlscan,
)
from hawkeye.models import CaseRecord

NOW = datetime(2026, 8, 2, tzinfo=UTC)
FIXTURE_RESPONSE = Path(__file__).parent / "fixtures" / "urlscan_public_response.json"


def _write_completed_case(
    root: Path,
    *,
    case_id: str = "source-case",
    allowed_crawl_hosts: list[str] | None = None,
) -> Path:
    directory = root / case_id
    directory.mkdir(parents=True)
    case = CaseRecord(
        case_id=case_id,
        seed_url="https://seed.example.com/",
        final_url="https://seed.example.com/",
        status="completed",
        started_at=NOW,
        completed_at=NOW,
        allowed_crawl_hosts=allowed_crawl_hosts or [],
    )
    (directory / "case.json").write_text(
        f"{json.dumps(case.model_dump(mode='json'), indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )
    return directory


def _fixture_source() -> UrlscanPublicSearchSource:
    return UrlscanPublicSearchSource(response_file=FIXTURE_RESPONSE)


def test_fixture_replay_creates_evidence_backed_pending_leads(tmp_path: Path) -> None:
    case_directory = _write_completed_case(tmp_path / "cases")
    output = tmp_path / "discovery"

    result = discover_case(
        case_directory,
        output_directory=output,
        source=_fixture_source(),
        limit=10,
        timeout_seconds=10.0,
    )

    document = result.document
    assert result.directory == output.resolve()
    assert document.source_name == "urlscan_public"
    assert document.response_evidence.collection_mode == "fixture_replay"
    assert (
        document.response_evidence.sha256
        == hashlib.sha256(FIXTURE_RESPONSE.read_bytes()).hexdigest()
    )
    assert (output / document.response_evidence.path).read_bytes() == FIXTURE_RESPONSE.read_bytes()
    assert [candidate.hostname for candidate in document.candidates] == [
        "candidate.example.org",
        "mirror.example.net",
        "www.seed.example.com",
    ]
    assert all(candidate.status == "pending" for candidate in document.candidates)
    assert all(candidate.relationship is None for candidate in document.candidates)
    assert document.candidates[2].scope_relation == "same_registrable_domain_external_host"
    assert document.excluded_observation_count == 3
    assert {
        observation.exclusion_reason
        for observation in document.observations
        if observation.candidate_decision == "excluded"
    } == {
        "ip_literal_candidate",
        "same_observed_host_as_source",
        "unsupported_url_scheme",
    }
    persisted = json.loads((output / "external-discovery.json").read_text(encoding="utf-8"))
    assert persisted["schema_version"] == "0.4.0"
    assert persisted["response_evidence"]["path"] == "source-response.json"
    assert persisted["candidate_document_path"] == "external-candidates.json"
    candidate_document = json.loads(
        (output / persisted["candidate_document_path"]).read_text(encoding="utf-8")
    )
    assert candidate_document["schema_version"] == "0.2.0"
    assert all(
        candidate["reasons"][0]["reason_type"] == "external_discovery"
        and candidate["reasons"][0]["weight"] == 5
        for candidate in candidate_document["candidates"]
    )
    metadata = json.loads(
        (output / document.response_evidence.metadata_path).read_text(encoding="utf-8")
    )
    assert metadata["response_sha256"] == document.response_evidence.sha256
    assert metadata["response_bytes"] == len(FIXTURE_RESPONSE.read_bytes())
    assert metadata["result_limit"] == 10


def test_source_transport_is_bounded_and_does_not_resolve_query_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def fake_transport(
        request_url: str,
        headers: object,
        timeout_seconds: float,
        max_bytes: int,
    ) -> bytes:
        observed.update(
            request_url=request_url,
            headers=headers,
            timeout_seconds=timeout_seconds,
            max_bytes=max_bytes,
        )
        return FIXTURE_RESPONSE.read_bytes()

    def fail_dns(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("fixture transport must not resolve DNS")

    monkeypatch.setattr(socket, "getaddrinfo", fail_dns)
    source = UrlscanPublicSearchSource(transport=fake_transport)

    response = source.collect("seed.example.com", limit=3, timeout_seconds=5.0)

    assert response.collection_mode == "live"
    assert "q=page.domain%3Aseed.example.com" in str(observed["request_url"])
    assert "size=3" in str(observed["request_url"])
    assert observed["timeout_seconds"] == 5.0
    assert observed["max_bytes"] == 1_000_000
    assert len(response.results) == 3


def test_discovery_does_not_rediscover_a_known_seed_or_final_hostname(tmp_path: Path) -> None:
    case_directory = _write_completed_case(
        tmp_path / "cases",
        allowed_crawl_hosts=["seed.example.com", "www.seed.example.com"],
    )

    result = discover_case(
        case_directory,
        output_directory=tmp_path / "discovery",
        source=_fixture_source(),
    )

    assert [candidate.hostname for candidate in result.document.candidates] == [
        "candidate.example.org",
        "mirror.example.net",
    ]
    known_host_observation = next(
        observation
        for observation in result.document.observations
        if observation.observed_url == "https://www.seed.example.com/promo"
    )
    assert known_host_observation.candidate_decision == "excluded"
    assert known_host_observation.exclusion_reason == "same_observed_host_as_source"


def test_source_rejects_invalid_limits_and_oversized_fixture(tmp_path: Path) -> None:
    source = _fixture_source()

    with pytest.raises(ValueError, match="between 1 and 20"):
        source.collect("seed.example.com", limit=21, timeout_seconds=1.0)

    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"x" * 1_000_001)
    oversized_source = UrlscanPublicSearchSource(response_file=oversized)
    with pytest.raises(ExternalDiscoverySourceError, match="exceeds byte limit"):
        oversized_source.collect("seed.example.com", limit=1, timeout_seconds=1.0)


def test_discovery_rejects_incomplete_cases_and_output_inside_case(tmp_path: Path) -> None:
    case_directory = _write_completed_case(tmp_path / "cases")
    case_payload = json.loads((case_directory / "case.json").read_text(encoding="utf-8"))
    case_payload["status"] = "running"
    (case_directory / "case.json").write_text(
        f"{json.dumps(case_payload, indent=2, sort_keys=True)}\n", encoding="utf-8"
    )

    with pytest.raises(ExternalDiscoveryInputError, match="not completed"):
        discover_case(
            case_directory,
            output_directory=tmp_path / "discovery",
            source=_fixture_source(),
        )

    completed_case = _write_completed_case(tmp_path / "other-cases", case_id="completed-case")
    with pytest.raises(ExternalDiscoveryInputError, match="inside the source case"):
        discover_case(
            completed_case,
            output_directory=completed_case / "external-discovery",
            source=_fixture_source(),
        )


def test_cli_replays_a_source_fixture_without_network(tmp_path: Path) -> None:
    case_directory = _write_completed_case(tmp_path / "cases")
    output = tmp_path / "discovery"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "hawkeye",
            "discover",
            str(case_directory),
            "--output",
            str(output),
            "--response-file",
            str(FIXTURE_RESPONSE),
            "--limit",
            "3",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    summary = json.loads(completed.stdout)
    assert summary["status"] == "completed"
    assert summary["source_name"] == "urlscan_public"
    assert summary["collection_mode"] == "fixture_replay"
    assert summary["candidate_count"] == 3
    assert (output / "external-discovery.json").is_file()


def test_live_source_validates_its_fixed_endpoint_before_the_http_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, int]] = []

    def resolver(hostname: str, port: int) -> list[str]:
        calls.append((hostname, port))
        return ["93.184.216.34"]

    observed_request_urls: list[str] = []

    def fake_http_get(request_url: str, *_args: object, **_kwargs: object) -> bytes:
        observed_request_urls.append(request_url)
        return FIXTURE_RESPONSE.read_bytes()

    source = UrlscanPublicSearchSource(safety_policy=SafetyPolicy(resolver=resolver))
    monkeypatch.setattr(urlscan, "_bounded_json_get", fake_http_get)

    source.collect("seed.example.com", limit=1, timeout_seconds=1.0)

    assert calls == [("urlscan.io", 443)]
    assert observed_request_urls == [
        "https://urlscan.io/api/v1/search/?q=page.domain%3Aseed.example.com&size=1"
    ]
