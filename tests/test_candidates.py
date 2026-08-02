"""Deterministic V0.2 candidate-generation coverage without external network access."""

from __future__ import annotations

import hashlib
import json
import socket
from datetime import UTC, datetime
from pathlib import Path

import pytest

from hawkeye.candidates import generate_candidates
from hawkeye.collector.safety import SafetyPolicy
from hawkeye.models import (
    CaptureOutcome,
    CaseRecord,
    CrawlFrontierRecord,
    CrawlPageRecord,
    EvidenceRecord,
    ExtractedEntity,
    RedirectRecord,
)
from hawkeye.pipeline import investigate

NOW = datetime(2026, 8, 2, tzinfo=UTC)


def _case(case_id: str, final_url: str) -> CaseRecord:
    return CaseRecord(
        case_id=case_id,
        seed_url=final_url,
        final_url=final_url,
        status="completed",
        started_at=NOW,
        completed_at=NOW,
        navigation_status="captured",
        capture_outcome=CaptureOutcome.CONTENT,
        content_usable=True,
    )


def _page(evidence_id: str, url: str, *, usable: bool = True) -> CrawlPageRecord:
    return CrawlPageRecord(
        id="page-001",
        url=url,
        normalized_url=url,
        depth=0,
        state="completed",
        final_url=url,
        navigation_status="captured",
        capture_outcome=CaptureOutcome.CONTENT if usable else CaptureOutcome.BOT_CHALLENGE,
        content_usable=usable,
        html_evidence_id=evidence_id,
    )


def _evidence(evidence_id: str, url: str, *, evidence_type: str = "html_page") -> EvidenceRecord:
    return EvidenceRecord(
        id=evidence_id,
        type=evidence_type,  # type: ignore[arg-type]
        source_url=url,
        path=f"pages/{evidence_id}.html",
        collected_at=NOW,
        sha256="0" * 64,
        page_id="page-001",
    )


def _entity(
    entity_id: str, entity_type: str, value: str, evidence_id: str, source_url: str
) -> ExtractedEntity:
    return ExtractedEntity(
        id=entity_id,
        type=entity_type,
        value=value,
        normalized_value=value,
        source_evidence_id=evidence_id,
        source_url=source_url,
        extraction_method="fixture",
        confidence=1.0,
    )


def _generate(
    *,
    tmp_path: Path,
    entities: list[ExtractedEntity],
    frontier: list[CrawlFrontierRecord] | None = None,
    corpus_root: Path | None = None,
) -> object:
    source_url = "https://www.source.example.com/"
    source_evidence = _evidence("evidence-current", source_url)
    return generate_candidates(
        case=_case("current-case", source_url),
        pages=[_page(source_evidence.id, source_url)],
        evidence=[source_evidence],
        entities=entities,
        frontier=frontier or [],
        corpus_root=corpus_root,
        current_case_directory=tmp_path / "current-case",
    )


def _write_corpus_case(
    root: Path,
    *,
    case_id: str,
    final_url: str,
    entities: list[ExtractedEntity],
    usable: bool = True,
) -> None:
    directory = root / case_id
    directory.mkdir(parents=True)
    artifact = directory / "pages" / "page-001.html"
    artifact.parent.mkdir()
    artifact_content = f"<html><body>{case_id}</body></html>".encode()
    artifact.write_bytes(artifact_content)
    evidence = _evidence("evidence-historical", final_url).model_copy(
        update={
            "path": "pages/page-001.html",
            "sha256": hashlib.sha256(artifact_content).hexdigest(),
        }
    )
    payloads = {
        "case.json": _case(case_id, final_url).model_dump(mode="json"),
        "pages.json": [_page(evidence.id, final_url, usable=usable).model_dump(mode="json")],
        "evidence.json": [evidence.model_dump(mode="json")],
        "entities.json": [entity.model_dump(mode="json") for entity in entities],
    }
    for name, payload in payloads.items():
        (directory / name).write_text(
            f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8"
        )


def test_external_link_creates_pending_candidate_without_a_corpus(tmp_path: Path) -> None:
    source_url = "https://www.source.example.com/"
    generation = _generate(
        tmp_path=tmp_path,
        entities=[
            _entity(
                "entity-001",
                "external_link",
                "https://offers.related.example.net/path",
                "evidence-current",
                source_url,
            )
        ],
    )

    candidate = generation.document.candidates[0]
    assert candidate.registrable_domain == "example.net"
    assert candidate.observed_hosts == ["offers.related.example.net"]
    assert candidate.status == "pending"
    assert candidate.relationship is None
    assert candidate.discovery_priority_score == 10
    assert candidate.reasons[0].reason_type == "external_link"
    assert candidate.reasons[0].supporting_evidence_ids == ["evidence-current"]
    assert generation.observations[0].candidate_decision == "accepted"


def test_same_registrable_domain_different_hostname_remains_a_candidate(tmp_path: Path) -> None:
    source_url = "https://www.source.example.com/"
    generation = _generate(
        tmp_path=tmp_path,
        entities=[
            _entity(
                "entity-001",
                "external_link",
                "https://backup.source.example.com/landing",
                "evidence-current",
                source_url,
            )
        ],
    )

    candidate = generation.document.candidates[0]
    assert candidate.candidate_id == "candidate-host:backup.source.example.com"
    assert candidate.hostname == "backup.source.example.com"
    assert candidate.registrable_domain == "example.com"
    assert candidate.scope_relation == "same_registrable_domain_external_host"


def test_private_suffix_tenants_remain_distinct_hostname_candidates(tmp_path: Path) -> None:
    source_url = "https://www.source.example.com/"
    generation = _generate(
        tmp_path=tmp_path,
        entities=[
            _entity(
                "entity-a",
                "external_link",
                "https://user-a.github.io/",
                "evidence-current",
                source_url,
            ),
            _entity(
                "entity-b",
                "external_link",
                "https://user-b.github.io/",
                "evidence-current",
                source_url,
            ),
        ],
    )

    assert [candidate.hostname for candidate in generation.document.candidates] == [
        "user-a.github.io",
        "user-b.github.io",
    ]
    assert [candidate.registrable_domain for candidate in generation.document.candidates] == [
        "user-a.github.io",
        "user-b.github.io",
    ]
    assert {candidate.suffix_type for candidate in generation.document.candidates} == {"private"}


def test_network_redirect_creates_pending_candidate_from_network_evidence(tmp_path: Path) -> None:
    source_url = "https://www.source.example.com/"
    network_evidence = _evidence("evidence-network-001", source_url, evidence_type="network_event")
    page = _page("evidence-current", source_url).model_copy(
        update={
            "redirect_evidence_id": network_evidence.id,
            "redirects": [
                RedirectRecord(
                    source_url="https://www.source.example.com/redirect",
                    destination_url="https://redirect.related.example.org/landing",
                    status_code=302,
                    raw_location="https://redirect.related.example.org/landing",
                )
            ],
        }
    )
    generation = generate_candidates(
        case=_case("current-case", source_url),
        pages=[page],
        evidence=[_evidence("evidence-current", source_url), network_evidence],
        entities=[],
        frontier=[],
        corpus_root=None,
        current_case_directory=tmp_path / "current-case",
    )

    candidate = generation.document.candidates[0]
    assert candidate.registrable_domain == "example.org"
    assert candidate.discovery_priority_score == 30
    assert candidate.reasons[0].reason_type == "external_redirect"
    assert candidate.reasons[0].discovery_method == "network_redirect"
    assert candidate.reasons[0].supporting_evidence_ids == ["evidence-network-001"]
    assert generation.observations[0].details["raw_location"] == (
        "https://redirect.related.example.org/landing"
    )


def test_subresource_redirect_is_recorded_but_never_promoted_to_a_candidate(tmp_path: Path) -> None:
    source_url = "https://www.source.example.com/"
    network_evidence = _evidence("evidence-network-001", source_url, evidence_type="network_event")
    page = _page("evidence-current", source_url).model_copy(
        update={
            "redirect_evidence_id": network_evidence.id,
            "redirects": [
                RedirectRecord(
                    source_url="https://www.source.example.com/redirect",
                    destination_url="https://redirect.related.example.org/landing",
                    status_code=302,
                    raw_location="/landing",
                    resource_type="image",
                    is_top_level_navigation=False,
                )
            ],
        }
    )
    generation = generate_candidates(
        case=_case("current-case", source_url),
        pages=[page],
        evidence=[_evidence("evidence-current", source_url), network_evidence],
        entities=[],
        frontier=[],
        corpus_root=None,
        current_case_directory=tmp_path / "current-case",
    )

    assert generation.document.candidates == []
    assert generation.observations[0].exclusion_reason == "non_top_level_or_non_document_redirect"
    assert generation.observations[0].details["resource_type"] == "image"


def test_shared_telegram_has_two_sided_local_corpus_evidence(tmp_path: Path) -> None:
    source_url = "https://www.source.example.com/"
    corpus = tmp_path / "corpus"
    historical_url = "https://www.related.example.net/"
    _write_corpus_case(
        corpus,
        case_id="historical-case",
        final_url=historical_url,
        entities=[
            _entity(
                "entity-historical",
                "telegram",
                "@sharedadmin",
                "evidence-historical",
                historical_url,
            )
        ],
    )
    generation = _generate(
        tmp_path=tmp_path,
        corpus_root=corpus,
        entities=[
            _entity(
                "entity-current",
                "telegram",
                "@sharedadmin",
                "evidence-current",
                source_url,
            )
        ],
    )

    candidate = generation.document.candidates[0]
    reason = candidate.reasons[0]
    assert candidate.registrable_domain == "example.net"
    assert candidate.discovery_priority_score == 35
    assert reason.reason_type == "shared_telegram"
    assert reason.signal_quality == "strong"
    assert reason.corpus_frequency == reason.corpus_case_count == reason.corpus_domain_count == 1
    assert reason.source_case_ids == ["current-case", "historical-case"]
    assert set(reason.supporting_evidence_ids) == {"evidence-current", "evidence-historical"}
    assert {(ref.case_id, ref.evidence_id) for ref in reason.supporting_evidence_refs} == {
        ("current-case", "evidence-current"),
        ("historical-case", "evidence-historical"),
    }
    assert generation.document.corpus.case_ids == ["historical-case"]
    assert generation.document.corpus.case_count == 1
    assert len(generation.document.corpus.manifest_sha256) == 64


def test_repeated_signal_observations_do_not_inflate_a_candidate_score(tmp_path: Path) -> None:
    source_url = "https://www.source.example.com/"
    corpus = tmp_path / "corpus"
    historical_url = "https://www.related.example.net/"
    _write_corpus_case(
        corpus,
        case_id="historical-case",
        final_url=historical_url,
        entities=[
            _entity(
                "entity-historical",
                "telegram",
                "@sharedadmin",
                "evidence-historical",
                historical_url,
            )
        ],
    )
    generation = _generate(
        tmp_path=tmp_path,
        corpus_root=corpus,
        entities=[
            _entity(
                "entity-current-a",
                "telegram",
                "@sharedadmin",
                "evidence-current",
                source_url,
            ),
            _entity(
                "entity-current-b",
                "telegram",
                "@sharedadmin",
                "evidence-current",
                source_url,
            ),
        ],
    )

    candidate = generation.document.candidates[0]
    assert candidate.discovery_priority_score == 35
    assert [reason.reason_type for reason in candidate.reasons] == ["shared_telegram"]


def test_distinct_shared_telegram_values_are_retained_but_scored_once(tmp_path: Path) -> None:
    source_url = "https://www.source.example.com/"
    corpus = tmp_path / "corpus"
    historical_url = "https://www.related.example.net/"
    _write_corpus_case(
        corpus,
        case_id="historical-case",
        final_url=historical_url,
        entities=[
            _entity(
                "entity-historical-a",
                "telegram",
                "@adminshared",
                "evidence-historical",
                historical_url,
            ),
            _entity(
                "entity-historical-b",
                "telegram",
                "@supportshared",
                "evidence-historical",
                historical_url,
            ),
        ],
    )
    generation = _generate(
        tmp_path=tmp_path,
        corpus_root=corpus,
        entities=[
            _entity(
                "entity-current-a",
                "telegram",
                "@adminshared",
                "evidence-current",
                source_url,
            ),
            _entity(
                "entity-current-b",
                "telegram",
                "@supportshared",
                "evidence-current",
                source_url,
            ),
        ],
    )

    candidate = generation.document.candidates[0]
    assert candidate.discovery_priority_score == 35
    assert [reason.signal_value for reason in candidate.reasons] == [
        "@adminshared",
        "@supportshared",
    ]


def test_direct_and_shared_reasons_merge_for_the_same_candidate(tmp_path: Path) -> None:
    source_url = "https://www.source.example.com/"
    corpus = tmp_path / "corpus"
    historical_url = "https://www.related.example.net/"
    _write_corpus_case(
        corpus,
        case_id="historical-case",
        final_url=historical_url,
        entities=[
            _entity(
                "entity-historical",
                "telegram",
                "@sharedadmin",
                "evidence-historical",
                historical_url,
            )
        ],
    )
    generation = _generate(
        tmp_path=tmp_path,
        corpus_root=corpus,
        entities=[
            _entity(
                "entity-link",
                "external_link",
                "https://www.related.example.net/offer",
                "evidence-current",
                source_url,
            ),
            _entity(
                "entity-telegram",
                "telegram",
                "@sharedadmin",
                "evidence-current",
                source_url,
            ),
        ],
    )

    candidate = generation.document.candidates[0]
    assert candidate.discovery_priority_score == 45
    assert {reason.reason_type for reason in candidate.reasons} == {
        "external_link",
        "shared_telegram",
    }


def test_exact_uncommon_assets_match_but_common_asset_providers_are_suppressed(
    tmp_path: Path,
) -> None:
    source_url = "https://www.source.example.com/"
    corpus = tmp_path / "corpus"
    historical_url = "https://www.related.example.net/"
    historical_asset = "https://assets.unusual.example.org/build-77.js?b=2&a=1"
    current_asset = "https://assets.unusual.example.org/build-77.js?a=1&b=2"
    _write_corpus_case(
        corpus,
        case_id="historical-case",
        final_url=historical_url,
        entities=[
            _entity(
                "entity-historical",
                "external_asset_url",
                historical_asset,
                "evidence-historical",
                historical_url,
            )
        ],
    )
    generation = _generate(
        tmp_path=tmp_path,
        corpus_root=corpus,
        entities=[
            _entity(
                "entity-uncommon",
                "external_asset_url",
                current_asset,
                "evidence-current",
                source_url,
            ),
            _entity(
                "entity-common",
                "external_asset_url",
                "https://cdnjs.cloudflare.com/ajax/libs/library/1.0.0/library.js",
                "evidence-current",
                source_url,
            ),
        ],
    )

    candidate = generation.document.candidates[0]
    assert candidate.discovery_priority_score == 20
    assert candidate.reasons[0].reason_type == "shared_exact_asset_url"
    assert any(
        observation.exclusion_reason == "common_asset_provider"
        for observation in generation.observations
    )


def test_unusable_corpus_self_matches_and_invalid_candidates_are_excluded(tmp_path: Path) -> None:
    source_url = "https://www.source.example.com/"
    corpus = tmp_path / "corpus"
    unusable_url = "https://www.related.example.net/"
    _write_corpus_case(
        corpus,
        case_id="unusable-case",
        final_url=unusable_url,
        usable=False,
        entities=[
            _entity(
                "entity-historical",
                "telegram",
                "@sharedadmin",
                "evidence-historical",
                unusable_url,
            )
        ],
    )
    generation = _generate(
        tmp_path=tmp_path,
        corpus_root=corpus,
        entities=[
            _entity(
                "entity-ip",
                "external_link",
                "https://8.8.8.8/",
                "evidence-current",
                source_url,
            ),
            _entity(
                "entity-suffix",
                "external_link",
                "https://com/",
                "evidence-current",
                source_url,
            ),
            _entity(
                "entity-private-suffix",
                "external_link",
                "https://github.io/",
                "evidence-current",
                source_url,
            ),
            _entity(
                "entity-self",
                "external_link",
                "https://www.source.example.com/other",
                "evidence-current",
                source_url,
            ),
            _entity(
                "entity-telegram",
                "telegram",
                "@sharedadmin",
                "evidence-current",
                source_url,
            ),
        ],
    )

    assert generation.document.candidates == []
    assert generation.document.excluded_observation_count == 4
    assert {observation.exclusion_reason for observation in generation.observations} == {
        "ip_literal_candidate",
        "not_registrable_domain",
        "same_observed_host_as_source",
    }


def test_common_external_reference_is_retained_as_an_excluded_observation(tmp_path: Path) -> None:
    source_url = "https://www.source.example.com/"
    generation = _generate(
        tmp_path=tmp_path,
        entities=[
            _entity(
                "entity-reference",
                "external_link",
                "https://t.me/FixtureAdmin",
                "evidence-current",
                source_url,
            )
        ],
    )

    assert generation.document.candidates == []
    assert generation.observations[0].exclusion_reason == "common_external_reference"


def test_candidate_ids_and_order_are_deterministic_for_the_same_corpus(tmp_path: Path) -> None:
    source_url = "https://www.source.example.com/"
    corpus = tmp_path / "corpus"
    historical_url = "https://www.related.example.net/"
    _write_corpus_case(
        corpus,
        case_id="historical-case",
        final_url=historical_url,
        entities=[
            _entity(
                "entity-historical",
                "telegram",
                "@sharedadmin",
                "evidence-historical",
                historical_url,
            )
        ],
    )
    entities = [
        _entity(
            "entity-direct",
            "external_link",
            "https://backup.source.example.com/",
            "evidence-current",
            source_url,
        ),
        _entity(
            "entity-shared",
            "telegram",
            "@sharedadmin",
            "evidence-current",
            source_url,
        ),
    ]
    first = _generate(tmp_path=tmp_path, corpus_root=corpus, entities=entities)
    second = _generate(tmp_path=tmp_path, corpus_root=corpus, entities=entities)

    assert [candidate.model_dump() for candidate in first.document.candidates] == [
        candidate.model_dump() for candidate in second.document.candidates
    ]
    assert [observation.model_dump() for observation in first.observations] == [
        observation.model_dump() for observation in second.observations
    ]
    assert first.document.corpus.manifest_sha256 == second.document.corpus.manifest_sha256


def test_corrupt_corpus_entries_are_visible_in_the_snapshot(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    (corpus / "corrupt-case").mkdir(parents=True)

    generation = _generate(tmp_path=tmp_path, corpus_root=corpus, entities=[])

    assert generation.document.corpus.case_ids == []
    assert [exclusion.model_dump() for exclusion in generation.document.corpus.excluded_cases] == [
        {
            "case_id": None,
            "directory_name": "corrupt-case",
            "reason": "malformed_or_incompatible_case_artifacts",
        }
    ]


def test_legacy_case_without_candidate_fields_remains_usable_as_a_local_corpus_case(
    tmp_path: Path,
) -> None:
    source_url = "https://www.source.example.com/"
    corpus = tmp_path / "corpus"
    historical_url = "https://www.related.example.net/"
    _write_corpus_case(
        corpus,
        case_id="legacy-case",
        final_url=historical_url,
        entities=[
            _entity(
                "entity-historical",
                "telegram",
                "@sharedadmin",
                "evidence-historical",
                historical_url,
            )
        ],
    )
    case_path = corpus / "legacy-case" / "case.json"
    case_payload = json.loads(case_path.read_text(encoding="utf-8"))
    case_payload.pop("candidate_count")
    case_path.write_text(f"{json.dumps(case_payload, indent=2)}\n", encoding="utf-8")

    generation = _generate(
        tmp_path=tmp_path,
        corpus_root=corpus,
        entities=[
            _entity(
                "entity-current",
                "telegram",
                "@sharedadmin",
                "evidence-current",
                source_url,
            )
        ],
    )

    assert generation.document.candidates[0].hostname == "www.related.example.net"


def test_candidate_generation_performs_no_dns_resolution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fail_dns(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("candidate generation must not resolve DNS")

    monkeypatch.setattr(socket, "getaddrinfo", fail_dns)
    source_url = "https://www.source.example.com/"
    generation = _generate(
        tmp_path=tmp_path,
        entities=[
            _entity(
                "entity-direct",
                "external_link",
                "https://offers.related.example.net/offer",
                "evidence-current",
                source_url,
            )
        ],
    )

    assert generation.document.candidates[0].hostname == "offers.related.example.net"


def test_pipeline_persists_candidate_artifacts_without_crawling_a_candidate(
    fixture_server_url: str, tmp_path: Path
) -> None:
    result = investigate(
        f"{fixture_server_url}crawl-candidate-root",
        output=tmp_path / "cases",
        case_id="candidate-pipeline-case",
        timeout_seconds=15,
        max_pages=1,
        max_depth=0,
        safety_policy=SafetyPolicy(allow_loopback_for_testing=True),
    )

    case_root = Path(result.case_directory)
    document = json.loads((case_root / "candidates.json").read_text(encoding="utf-8"))
    observations = json.loads(
        (case_root / "candidate_observations.json").read_text(encoding="utf-8")
    )
    assert result.case.page_count == 1
    assert result.case.candidate_count == 1
    assert document["candidates"][0]["registrable_domain"] == "example.net"
    assert observations[0]["details"]["anchor_text"] == "External candidate"
    assert (case_root / "candidate_observations.json").is_file()
