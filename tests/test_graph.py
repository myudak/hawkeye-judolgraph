"""Graph construction and evidence-integrity tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from hawkeye.extraction import extract_entities
from hawkeye.graph import build_graph, validate_graph_evidence
from hawkeye.models import CaseRecord, EvidenceRecord, GraphEdge


def _graph_inputs() -> tuple[CaseRecord, list[EvidenceRecord], list]:
    now = datetime.now(UTC)
    case = CaseRecord(
        case_id="fixture-case",
        seed_url="https://fixture.test/",
        status="completed",
        started_at=now,
        completed_at=now,
        final_url="https://fixture.test/",
        page_count=1,
    )
    evidence = [
        EvidenceRecord(
            id="evidence-page-001",
            type="html_page",
            source_url="https://fixture.test/",
            path="pages/page-001.html",
            collected_at=now,
            sha256="a" * 64,
        ),
        EvidenceRecord(
            id="evidence-screenshot-001",
            type="screenshot",
            source_url="https://fixture.test/",
            path="screenshots/page-001.png",
            collected_at=now,
            sha256="b" * 64,
            viewport={"width": 1440, "height": 1024},
            image_dimensions={"width": 1440, "height": 1024},
        ),
    ]
    html = (Path(__file__).parent / "fixtures" / "landing.html").read_text(encoding="utf-8")
    entities = extract_entities(
        html,
        seed_url=case.seed_url,
        final_url="https://fixture.test/",
        source_evidence_id="evidence-page-001",
    )
    return case, evidence, entities


def test_builds_required_nodes_and_evidence_backed_edges() -> None:
    case, evidence, entities = _graph_inputs()
    graph = build_graph(case=case, evidence=evidence, entities=entities)

    assert {node.type for node in graph.nodes} >= {
        "case",
        "domain",
        "page",
        "screenshot",
        "telegram",
        "whatsapp_or_phone",
        "referral",
        "external_asset_domain",
    }
    assert {edge.type for edge in graph.edges} >= {
        "started_from",
        "contains_page",
        "captured_as",
        "links_to",
        "mentions",
        "uses_referral",
        "loads_asset_from",
    }
    structural = {"started_from", "resolved_to", "contains_page", "captured_as"}
    non_structural = [edge for edge in graph.edges if edge.type not in structural]
    assert non_structural
    assert all(edge.evidence_id == "evidence-page-001" for edge in non_structural)
    assert all(
        edge.source_url and edge.extraction_method and edge.confidence is not None
        for edge in non_structural
    )
    validate_graph_evidence(graph, evidence)
    assert not any(edge.source == edge.target for edge in graph.edges)


def test_extracted_edge_schema_rejects_missing_evidence_fields() -> None:
    with pytest.raises(ValidationError, match="requires evidence"):
        GraphEdge(id="bad", source="page:1", target="telegram:@x", type="mentions")
