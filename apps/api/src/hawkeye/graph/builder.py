"""Build an evidence-backed graph for one bounded same-site crawl case."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Literal
from urllib.parse import urlsplit

from hawkeye.models import (
    STRUCTURAL_EDGE_TYPES,
    CaseRecord,
    CrawlPageRecord,
    EvidenceRecord,
    ExtractedEntity,
    GraphDocument,
    GraphEdge,
    GraphNode,
)

StructuralEdgeType = Literal["started_from", "resolved_to", "contains_page", "captured_as"]
EvidenceEdgeType = Literal[
    "discovered_via_link",
    "links_to",
    "mentions",
    "uses_referral",
    "loads_asset_from",
]


def build_graph(
    *,
    case: CaseRecord,
    evidence: list[EvidenceRecord],
    entities: list[ExtractedEntity],
    pages: list[CrawlPageRecord] | None = None,
) -> GraphDocument:
    """Create graph nodes and evidence-linked edges for V0 and V0.1 artifacts."""

    if case.final_url is None:
        raise ValueError("A completed graph requires a final URL")
    crawl_pages = pages or [_legacy_primary_page(case, evidence)]
    nodes: dict[str, GraphNode] = {}
    edges: dict[str, GraphEdge] = {}
    evidence_to_page = {
        record.id: record.page_id or _page_id_from_evidence_id(record.id) for record in evidence
    }

    case_node = _add_node(
        nodes,
        GraphNode(
            id=f"case:{case.case_id}",
            type="case",
            label=case.case_id,
            attributes={
                "seed_url": case.seed_url,
                "final_url": case.final_url,
                "allowed_crawl_hosts": case.allowed_crawl_hosts,
            },
        ),
    )
    seed_domain = _domain_node(nodes, case.seed_url)
    final_domain = _domain_node(nodes, case.final_url)
    _add_structural_edge(edges, case_node.id, seed_domain.id, "started_from")
    if seed_domain.id != final_domain.id:
        _add_structural_edge(edges, seed_domain.id, final_domain.id, "resolved_to")

    page_nodes: dict[str, GraphNode] = {}
    page_by_id = {page.id: page for page in crawl_pages}
    for page in crawl_pages:
        page_url = page.final_url or page.normalized_url
        page_node = _add_node(
            nodes,
            GraphNode(
                id=f"page:{page.id}",
                type="page",
                label=page_url,
                attributes={
                    "page_id": page.id,
                    "url": page_url,
                    "normalized_url": page.normalized_url,
                    "title": page.page_title,
                    "depth": page.depth,
                    "state": page.state,
                    "parent_page_id": page.parent_page_id,
                    "evidence_id": page.html_evidence_id,
                    "capture_outcome": (
                        page.capture_outcome.value if page.capture_outcome else None
                    ),
                    "content_usable": page.content_usable,
                    "classification_reasons": page.classification_reasons,
                    "skip_reason": page.skip_reason,
                    "duplicate_of_page_id": page.duplicate_of_page_id,
                    "blocked_request_count": len(page.blocked_requests),
                },
            ),
        )
        page_nodes[page.id] = page_node
        page_domain = _domain_node(nodes, page_url)
        _add_structural_edge(edges, page_domain.id, page_node.id, "contains_page")
        screenshot = _evidence_for_page(evidence, page.id, "screenshot")
        if screenshot is not None:
            screenshot_node = _add_node(
                nodes,
                GraphNode(
                    id=f"screenshot:{screenshot.id}",
                    type="screenshot",
                    label=screenshot.path,
                    attributes={"evidence_id": screenshot.id, "path": screenshot.path},
                ),
            )
            _add_structural_edge(edges, page_node.id, screenshot_node.id, "captured_as")

    for page in crawl_pages:
        if page.parent_page_id is None or page.source_evidence_id is None:
            continue
        parent_node = page_nodes.get(page.parent_page_id)
        child_node = page_nodes.get(page.id)
        parent_page = page_by_id.get(page.parent_page_id)
        if parent_node is None or child_node is None or parent_page is None:
            continue
        _add_discovery_edge(
            edges,
            parent_node.id,
            child_node.id,
            evidence_id=page.source_evidence_id,
            source_url=parent_page.final_url or parent_page.normalized_url,
            original_href=page.original_href,
            normalized_target=page.normalized_url,
            anchor_text=page.anchor_text,
            depth=page.depth,
        )

    for entity in entities:
        target = _target_for_entity(nodes, entity)
        if target is None:
            continue
        edge_type = _edge_type_for_entity(entity)
        if edge_type is None:
            continue
        source_page_id = evidence_to_page.get(entity.source_evidence_id) or "page-001"
        source_page = page_nodes.get(source_page_id)
        if source_page is None:
            raise ValueError(f"Entity source evidence does not map to a crawl page: {entity.id}")
        _add_evidence_edge(edges, source_page.id, target.id, edge_type, entity)

    graph = GraphDocument(
        nodes=sorted(nodes.values(), key=lambda node: node.id),
        edges=sorted(edges.values(), key=lambda edge: edge.id),
        metadata={
            "schema_version": "0.2.0",
            "case_id": case.case_id,
            "seed_url": case.seed_url,
            "final_url": case.final_url,
            "capture_outcome": case.capture_outcome.value if case.capture_outcome else None,
            "content_usable": case.content_usable,
            "page_count": case.page_count,
        },
    )
    validate_graph_evidence(graph, evidence)
    return graph


def validate_graph_evidence(graph: GraphDocument, evidence: Iterable[EvidenceRecord]) -> None:
    """Ensure each extracted edge has a complete pointer to a real evidence record."""

    known_evidence_ids = {record.id for record in evidence}
    node_ids = {node.id for node in graph.nodes}
    for edge in graph.edges:
        if edge.source not in node_ids or edge.target not in node_ids:
            raise ValueError(f"Graph edge references a missing node: {edge.id}")
        if edge.type in STRUCTURAL_EDGE_TYPES:
            continue
        if edge.evidence_id not in known_evidence_ids:
            raise ValueError(f"Graph edge references missing evidence: {edge.id}")
        if not edge.source_url or not edge.extraction_method or edge.confidence is None:
            raise ValueError(f"Graph edge is missing required evidence metadata: {edge.id}")


def _legacy_primary_page(case: CaseRecord, evidence: list[EvidenceRecord]) -> CrawlPageRecord:
    """Keep direct callers of the V0 graph builder compatible with one-page inputs."""

    html = _first_evidence_of_type(evidence, "html_page")
    screenshot = _first_evidence_of_type(evidence, "screenshot")
    return CrawlPageRecord(
        id="page-001",
        url=case.final_url or case.seed_url,
        normalized_url=case.final_url or case.seed_url,
        depth=0,
        state="completed",
        final_url=case.final_url,
        navigation_status=case.navigation_status,
        capture_outcome=case.capture_outcome,
        content_usable=case.content_usable,
        classification_reasons=case.classification_reasons,
        page_title=case.page_title,
        html_evidence_id=html.id,
        screenshot_evidence_id=screenshot.id,
        content_sha256=html.sha256,
    )


def _first_evidence_of_type(evidence: list[EvidenceRecord], evidence_type: str) -> EvidenceRecord:
    for record in evidence:
        if record.type == evidence_type:
            return record
    raise ValueError(f"Missing required evidence type: {evidence_type}")


def _evidence_for_page(
    evidence: list[EvidenceRecord], page_id: str, evidence_type: str
) -> EvidenceRecord | None:
    for record in evidence:
        if record.type == evidence_type and (
            record.page_id == page_id or _page_id_from_evidence_id(record.id) == page_id
        ):
            return record
    return None


def _page_id_from_evidence_id(evidence_id: str) -> str | None:
    if evidence_id.startswith("evidence-page-"):
        return evidence_id.removeprefix("evidence-")
    if evidence_id.startswith("evidence-screenshot-"):
        return f"page-{evidence_id.removeprefix('evidence-screenshot-')}"
    return None


def _domain_node(nodes: dict[str, GraphNode], url: str) -> GraphNode:
    hostname = _hostname(url)
    return _add_node(
        nodes,
        GraphNode(
            id=f"domain:{hostname}",
            type="domain",
            label=hostname,
            attributes={"hostname": hostname},
        ),
    )


def _target_for_entity(nodes: dict[str, GraphNode], entity: ExtractedEntity) -> GraphNode | None:
    if entity.type in {"internal_link", "external_link"}:
        return _domain_node(nodes, entity.normalized_value)
    if entity.type == "telegram":
        return _add_node(
            nodes,
            GraphNode(
                id=f"telegram:{entity.normalized_value}",
                type="telegram",
                label=entity.value,
                attributes={"handle": entity.normalized_value},
            ),
        )
    if entity.type == "whatsapp_or_phone":
        return _add_node(
            nodes,
            GraphNode(
                id=f"whatsapp_or_phone:{entity.normalized_value}",
                type="whatsapp_or_phone",
                label=entity.value,
                attributes=entity.details,
            ),
        )
    if entity.type == "referral":
        return _add_node(
            nodes,
            GraphNode(
                id=f"referral:{entity.normalized_value}",
                type="referral",
                label=entity.value,
                attributes=entity.details,
            ),
        )
    if entity.type == "external_asset_domain":
        return _add_node(
            nodes,
            GraphNode(
                id=f"external_asset_domain:{entity.normalized_value}",
                type="external_asset_domain",
                label=entity.value,
                attributes=entity.details,
            ),
        )
    if entity.type == "external_asset_url":
        return _add_node(
            nodes,
            GraphNode(
                id=f"external_asset_url:{entity.normalized_value}",
                type="external_asset_url",
                label=entity.value,
                attributes=entity.details,
            ),
        )
    return None


def _edge_type_for_entity(entity: ExtractedEntity) -> EvidenceEdgeType | None:
    if entity.type in {"internal_link", "external_link"}:
        return "links_to"
    if entity.type in {"telegram", "whatsapp_or_phone"}:
        return "mentions"
    if entity.type == "referral":
        return "uses_referral"
    if entity.type in {"external_asset_domain", "external_asset_url"}:
        return "loads_asset_from"
    return None


def _add_node(nodes: dict[str, GraphNode], node: GraphNode) -> GraphNode:
    existing = nodes.get(node.id)
    if existing is None:
        nodes[node.id] = node
        return node
    return existing


def _add_structural_edge(
    edges: dict[str, GraphEdge], source: str, target: str, edge_type: StructuralEdgeType
) -> None:
    edge = GraphEdge(
        id=_edge_id(source, target, edge_type, None), source=source, target=target, type=edge_type
    )
    edges.setdefault(edge.id, edge)


def _add_discovery_edge(
    edges: dict[str, GraphEdge],
    source: str,
    target: str,
    *,
    evidence_id: str,
    source_url: str,
    original_href: str | None,
    normalized_target: str,
    anchor_text: str | None,
    depth: int,
) -> None:
    edge_type: EvidenceEdgeType = "discovered_via_link"
    edge = GraphEdge(
        id=_edge_id(source, target, edge_type, evidence_id),
        source=source,
        target=target,
        type=edge_type,
        evidence_id=evidence_id,
        source_url=source_url,
        extraction_method="html_anchor",
        confidence=1.0,
        attributes={
            "original_href": original_href,
            "normalized_target": normalized_target,
            "anchor_text": anchor_text,
            "crawl_depth": depth,
        },
    )
    edges.setdefault(edge.id, edge)


def _add_evidence_edge(
    edges: dict[str, GraphEdge],
    source: str,
    target: str,
    edge_type: EvidenceEdgeType,
    entity: ExtractedEntity,
) -> None:
    edge = GraphEdge(
        id=_edge_id(source, target, edge_type, entity.source_evidence_id),
        source=source,
        target=target,
        type=edge_type,
        evidence_id=entity.source_evidence_id,
        source_url=entity.source_url,
        extraction_method=entity.extraction_method,
        confidence=entity.confidence,
    )
    edges.setdefault(edge.id, edge)


def _edge_id(source: str, target: str, edge_type: str, evidence_id: str | None) -> str:
    material = "|".join((source, target, edge_type, evidence_id or "structural"))
    return f"edge-{hashlib.sha256(material.encode('utf-8')).hexdigest()[:16]}"


def _hostname(url: str) -> str:
    hostname = urlsplit(url).hostname
    if not hostname:
        raise ValueError(f"URL does not have a hostname: {url}")
    return hostname.rstrip(".").lower()
