"""Fixture-based tests for deterministic entity extraction."""

from __future__ import annotations

from pathlib import Path

from hawkeye.extraction import extract_entities
from hawkeye.extraction.links import (
    extract_anchor_links,
    normalize_exact_asset_url,
    normalize_http_url,
)


def _fixture_html() -> str:
    return (Path(__file__).parent / "fixtures" / "landing.html").read_text(encoding="utf-8")


def _entities_by_type() -> dict[str, list[str]]:
    entities = extract_entities(
        _fixture_html(),
        seed_url="https://fixture.test/",
        final_url="https://fixture.test/",
        source_evidence_id="evidence-page-001",
    )
    grouped: dict[str, list[str]] = {}
    for entity in entities:
        grouped.setdefault(entity.type, []).append(entity.normalized_value)
    return grouped


def test_normalizes_relative_links_and_classifies_internal_external() -> None:
    assert (
        normalize_http_url("/inside#fragment", "https://fixture.test/base")
        == "https://fixture.test/inside"
    )
    assert normalize_http_url("mailto:test@example.test", "https://fixture.test/") is None

    from bs4 import BeautifulSoup

    links = extract_anchor_links(
        BeautifulSoup(_fixture_html(), "html.parser"), "https://fixture.test/"
    )
    assert {link.kind for link in links} == {"internal_link", "external_link"}
    assert "https://fixture.test/inside/path?invite=TEAM-7" in {link.url for link in links}


def test_extracts_required_entities_and_collapses_duplicates_deterministically() -> None:
    first = extract_entities(
        _fixture_html(),
        seed_url="https://fixture.test/",
        final_url="https://fixture.test/",
        source_evidence_id="evidence-page-001",
    )
    second = extract_entities(
        _fixture_html(),
        seed_url="https://fixture.test/",
        final_url="https://fixture.test/",
        source_evidence_id="evidence-page-001",
    )
    grouped = _entities_by_type()

    assert [entity.model_dump() for entity in first] == [entity.model_dump() for entity in second]
    assert grouped["page_title"] == ["fixture evidence landing"]
    assert grouped["telegram"] == ["@anotherteam", "@fixtureadmin"]
    assert grouped["whatsapp_or_phone"] == ["+6281234567890"]
    assert set(grouped["referral"]) == {"affiliate=AFF-42", "invite=TEAM-7"}
    assert set(grouped["external_asset_domain"]) == {
        "frames.asset.test",
        "images.asset.test",
        "scripts.asset.test",
        "styles.asset.test",
    }
    assert grouped["referenced_domain"] == ["fixture.test", "outbound.example", "t.me", "wa.me"]
    assert len(grouped["external_link"]) == 3


def test_entities_are_linked_to_the_html_evidence() -> None:
    entities = extract_entities(
        _fixture_html(),
        seed_url="https://fixture.test/",
        final_url="https://fixture.test/",
        source_evidence_id="evidence-page-001",
    )
    assert all(entity.source_evidence_id == "evidence-page-001" for entity in entities)
    assert all(entity.confidence == 1.0 for entity in entities)


def test_exact_asset_urls_sort_query_order_without_erasing_meaningful_values() -> None:
    first = normalize_exact_asset_url(
        "https://ASSETS.example.net/app.js?b=2&a=1#fragment", "https://fixture.test/"
    )
    second = normalize_exact_asset_url(
        "https://assets.example.net/app.js?a=1&b=2", "https://fixture.test/"
    )
    tenant_a = normalize_exact_asset_url(
        "https://assets.example.net/logo.png?tenant=a", "https://fixture.test/"
    )
    tenant_b = normalize_exact_asset_url(
        "https://assets.example.net/logo.png?tenant=b", "https://fixture.test/"
    )

    assert (
        first is not None and second is not None and tenant_a is not None and tenant_b is not None
    )
    assert first[1] == second[1] == "https://assets.example.net/app.js?a=1&b=2"
    assert tenant_a[1] != tenant_b[1]
