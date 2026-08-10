"""Idempotent event reducer for stable graph truth and a separate animation queue."""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit

from hawkeye.investigation.models import (
    CausalLink,
    GraphAnimation,
    InvestigationEvent,
    ProgressiveGraphEdge,
    ProgressiveGraphNode,
    ProgressiveGraphState,
)


def reduce_events(events: list[InvestigationEvent]) -> ProgressiveGraphState:
    nodes: dict[str, ProgressiveGraphNode] = {}
    edges: dict[str, ProgressiveGraphEdge] = {}
    applied: set[str] = set()
    timeline: list[InvestigationEvent] = []
    animations: list[GraphAnimation] = []
    assertion_edges: dict[str, str] = {}
    source_aliases: dict[str, str] = {}
    observation_nodes: dict[str, str] = {}
    for event in sorted(events, key=lambda item: item.sequence):
        if event.event_id in applied:
            continue
        applied.add(event.event_id)
        timeline.append(event)
        payload = event.payload
        if event.kind == "run.started":
            node_id = f"seed:{event.case_id}"
            nodes[node_id] = ProgressiveGraphNode(
                id=node_id,
                kind="seed_page",
                label=str(payload.get("seed_url", event.case_id)),
                status="observed",
                attributes={"case_id": event.case_id},
            )
            animations.append(
                GraphAnimation(sequence=event.sequence, animation="spawn-node", target_id=node_id)
            )
        elif event.kind == "artifact.captured":
            proposed_id = str(payload.get("node_id", f"page:{event.sequence}"))
            seed_id = f"seed:{event.case_id}"
            seed_node = nodes.get(seed_id)
            label = str(payload.get("label", proposed_id))
            root = bool(payload.get("root")) or (
                seed_node is not None and _same_public_url(seed_node.label, label)
            )
            node_id = seed_id if root else proposed_id
            if root:
                source_aliases[proposed_id] = node_id
            nodes[node_id] = ProgressiveGraphNode(
                id=node_id,
                kind="seed_page" if root else "collected_page",
                label=label,
                status="collected",
                attributes=payload,
            )
            animations.append(
                GraphAnimation(sequence=event.sequence, animation="spawn-node", target_id=node_id)
            )
            if not root and payload.get("parent_node_id"):
                parent_value = str(payload["parent_node_id"])
                parent = source_aliases.get(parent_value, parent_value)
                edge_id = f"crawl:{parent}:{node_id}"
                edges[edge_id] = ProgressiveGraphEdge(
                    id=edge_id,
                    source=parent,
                    target=node_id,
                    relation=str(payload.get("parent_relation", "crawled_same_site_page")),
                    appearance="solid",
                    supporting_event_ids=[event.event_id],
                )
                animations.append(
                    GraphAnimation(
                        sequence=event.sequence,
                        animation="draw-edge",
                        target_id=edge_id,
                    )
                )
        elif event.kind == "observation.created":
            observation_type = str(payload.get("observation_type", "public_contact"))
            kind, relation = _observation_semantics(observation_type)
            label = str(payload.get("normalized_value", f"observation:{event.sequence}"))
            source_value = str(payload.get("source_node_id", f"seed:{event.case_id}"))
            source = source_aliases.get(source_value, source_value)
            observation_id = str(payload.get("observation_id", ""))
            source_node = nodes.get(source)
            if (
                kind in {"external_destination", "redirect_target"}
                and source_node is not None
                and (
                    _same_public_url(source_node.label, label)
                    or (
                        kind == "external_destination"
                        and _same_public_host(source_node.label, label)
                    )
                )
            ):
                if observation_id:
                    observation_nodes[observation_id] = source
                animations.append(
                    GraphAnimation(
                        sequence=event.sequence, animation="pulse-node", target_id=source
                    )
                )
                continue
            proposed_node_id = str(payload.get("node_id", f"observation:{event.sequence}"))
            if kind in {"external_destination", "redirect_target"}:
                hostname = _public_hostname(label)
                node_id = f"{kind}:{hostname}" if hostname else proposed_node_id
                label = hostname or label
            elif kind == "public_claim":
                category = _claim_category(observation_type)
                node_id = f"claim:{source}:{category}"
            else:
                node_id = next(
                    (
                        node.id
                        for node in nodes.values()
                        if node.kind == kind
                        and node.label == label
                        and (
                            kind != "public_contact"
                            or node.attributes.get("observation_type") == observation_type
                        )
                    ),
                    proposed_node_id,
                )
            status: Literal["observed", "collected"] = (
                "collected" if payload.get("matched_case_id") else "observed"
            )
            existing = nodes.get(node_id)
            attributes = {**(existing.attributes if existing else {}), **payload}
            if kind == "public_claim":
                values = sorted({*attributes.get("values", []), label})
                observation_types = sorted(
                    {*attributes.get("observation_types", []), observation_type}
                )
                category = _claim_category(observation_type)
                attributes.update(
                    {
                        "claim_category": category,
                        "values": values,
                        "observation_types": observation_types,
                        "observation_count": len(values),
                    }
                )
                label = f"{category.replace('_', ' ').title()} · {', '.join(values[:4])}"
            elif kind in {"external_destination", "redirect_target"}:
                urls = sorted(
                    {*attributes.get("observed_urls", []), str(payload.get("normalized_value", ""))}
                )
                attributes["observed_urls"] = [item for item in urls if item]
            nodes[node_id] = ProgressiveGraphNode(
                id=node_id,
                kind=kind,
                label=label,
                status="collected" if existing and existing.status == "collected" else status,
                attributes=attributes,
            )
            if observation_id:
                observation_nodes[observation_id] = node_id
            edge_id = f"{relation}:{source}:{node_id}"
            existing_edge = edges.get(edge_id)
            edges[edge_id] = ProgressiveGraphEdge(
                id=edge_id,
                source=source,
                target=node_id,
                relation=relation,
                appearance="solid",
                supporting_event_ids=list(
                    dict.fromkeys(
                        [
                            *(existing_edge.supporting_event_ids if existing_edge else []),
                            event.event_id,
                        ]
                    )
                ),
                supporting_observation_ids=list(
                    dict.fromkeys(
                        [
                            *(existing_edge.supporting_observation_ids if existing_edge else []),
                            str(payload.get("observation_id", "")),
                        ]
                    )
                ),
            )
            animations.extend(
                [
                    GraphAnimation(
                        sequence=event.sequence, animation="spawn-node", target_id=node_id
                    ),
                    GraphAnimation(
                        sequence=event.sequence, animation="draw-edge", target_id=edge_id
                    ),
                ]
            )
        elif event.kind == "search.lead.discovered":
            label = str(payload.get("url", ""))
            node_id = _node_id_with_public_url(nodes, label) or (
                f"candidate:{payload.get('lead_id', event.sequence)}"
            )
            existing = nodes.get(node_id)
            display_label = _public_hostname(label) or label or node_id
            nodes[node_id] = ProgressiveGraphNode(
                id=node_id,
                kind="candidate_domain",
                label=display_label,
                status="lead",
                attributes={**(existing.attributes if existing else {}), **payload},
            )
            for edge_id, lead_edge in list(edges.items()):
                if lead_edge.target == node_id:
                    edges[edge_id] = lead_edge.model_copy(update={"appearance": "dashed"})
            animations.append(
                GraphAnimation(sequence=event.sequence, animation="spawn-node", target_id=node_id)
            )
        elif event.kind == "entity.matched":
            observation_id = str(payload.get("observation_id", ""))
            matched_node_id = observation_nodes.get(observation_id)
            node = nodes.get(matched_node_id or "")
            if node is not None:
                nodes[node.id] = node.model_copy(
                    update={
                        "status": "collected",
                        "attributes": {**node.attributes, **payload},
                    }
                )
                animations.append(
                    GraphAnimation(
                        sequence=event.sequence, animation="pulse-node", target_id=node.id
                    )
                )
        elif event.kind == "candidate_page.collected":
            proposed_id = str(payload.get("node_id", f"candidate-page:{event.sequence}"))
            label = str(payload.get("url", proposed_id))
            node_id = _node_id_with_public_url(nodes, label) or proposed_id
            source_aliases[proposed_id] = node_id
            existing = nodes.get(node_id)
            nodes[node_id] = ProgressiveGraphNode(
                id=node_id,
                kind="collected_page",
                label=label,
                status="collected",
                attributes={**(existing.attributes if existing else {}), **payload},
            )
            animations.append(
                GraphAnimation(sequence=event.sequence, animation="spawn-node", target_id=node_id)
            )
        elif event.kind == "assertion.proposed":
            assertion_id = str(payload["assertion_id"])
            subject = str(payload.get("subject", ""))
            object_value = str(payload.get("object", ""))
            source_value = str(
                payload.get(
                    "subject_node_id",
                    _node_id_with_label(nodes, subject) or f"seed:{event.case_id}",
                )
            )
            target_value = str(
                payload.get(
                    "object_node_id",
                    _node_id_with_label(nodes, object_value) or f"candidate-page:{event.sequence}",
                )
            )
            source = source_aliases.get(source_value, source_value)
            target = source_aliases.get(target_value, target_value)
            edge_id = f"assertion:{assertion_id}"
            assertion_edges[assertion_id] = edge_id
            edges[edge_id] = ProgressiveGraphEdge(
                id=edge_id,
                source=source,
                target=target,
                relation=str(payload.get("assertion_type", "candidate_related_to")),
                appearance="dashed",
                supporting_event_ids=[event.event_id],
                supporting_observation_ids=list(payload.get("supporting_observation_ids", [])),
            )
            animations.append(
                GraphAnimation(sequence=event.sequence, animation="draw-edge", target_id=edge_id)
            )
        elif event.kind.startswith("assertion."):
            assertion_id = str(payload.get("assertion_id", ""))
            review_edge_id = assertion_edges.get(assertion_id)
            edge = edges.get(review_edge_id or "")
            if edge is None:
                continue
            appearance = (
                "solid_emphasized"
                if event.kind == "assertion.verified"
                else "hidden"
                if event.kind == "assertion.rejected"
                else "dashed"
            )
            edges[edge.id] = edge.model_copy(
                update={
                    "appearance": appearance,
                    "supporting_event_ids": [*edge.supporting_event_ids, event.event_id],
                }
            )
            animations.append(
                GraphAnimation(
                    sequence=event.sequence, animation="pulse-node", target_id=edge.target
                )
            )
    return ProgressiveGraphState(
        nodes=sorted(nodes.values(), key=lambda item: item.id),
        edges=sorted(edges.values(), key=lambda item: item.id),
        timeline=timeline,
        causal_links=[
            CausalLink(event_id=event.event_id, causation_event_id=event.causation_event_id)
            for event in timeline
        ],
        animations=animations,
        applied_event_ids=[event.event_id for event in timeline],
    )


def _node_id_with_label(nodes: dict[str, ProgressiveGraphNode], label: str) -> str | None:
    """Resolve an assertion endpoint to an existing stable node without creating graph truth."""

    matches = [node for node in nodes.values() if node.label == label]
    return next((node.id for node in matches if node.status == "collected"), None) or next(
        (node.id for node in matches), None
    )


def _node_id_with_public_url(nodes: dict[str, ProgressiveGraphNode], label: str) -> str | None:
    exact = _node_id_with_label(nodes, label)
    if exact is not None:
        return exact
    hostname = _public_hostname(label)
    if not hostname:
        return None
    matches = [
        node
        for node in nodes.values()
        if node.kind in {"candidate_domain", "external_destination", "redirect_target"}
        and (_public_hostname(node.label) or node.label.casefold()) == hostname
    ]
    return next((node.id for node in matches if node.status == "collected"), None) or next(
        (node.id for node in matches), None
    )


def _same_public_url(left: str, right: str) -> bool:
    """Compare public URL identities without treating display-only slash variants as entities."""

    try:
        left_url = urlsplit(left)
        right_url = urlsplit(right)
    except ValueError:
        return left == right
    if not left_url.scheme or not right_url.scheme:
        return left == right
    return (
        left_url.scheme.lower(),
        left_url.netloc.lower(),
        left_url.path.rstrip("/") or "/",
        left_url.query,
    ) == (
        right_url.scheme.lower(),
        right_url.netloc.lower(),
        right_url.path.rstrip("/") or "/",
        right_url.query,
    )


def _same_public_host(left: str, right: str) -> bool:
    left_host = _public_hostname(left)
    right_host = _public_hostname(right)
    return bool(left_host and left_host == right_host)


def _observation_semantics(
    observation_type: str,
) -> tuple[
    Literal[
        "claimed_brand",
        "public_contact",
        "public_claim",
        "external_destination",
        "redirect_target",
    ],
    str,
]:
    if observation_type == "claimed_brand_identity":
        return "claimed_brand", "claims_brand"
    if observation_type == "public_outgoing_link":
        return "external_destination", "publicly_links_to"
    if observation_type == "public_redirect_target":
        return "redirect_target", "publicly_redirects_to"
    if observation_type in {
        "public_telegram_alias",
        "public_telegram_contact",
        "public_whatsapp_link",
        "public_phone_number",
        "public_email_address",
    }:
        return "public_contact", "publishes_public_contact"
    return "public_claim", "displays_public_claim"


def _claim_category(observation_type: str) -> str:
    if observation_type in {"public_payment_method", "public_payment_provider"}:
        return "payment_indicators"
    if observation_type == "public_offer_claim":
        return "offer_claims"
    if observation_type == "public_legal_or_license_claim":
        return "legal_claims"
    if observation_type == "public_referral_code":
        return "referral_markers"
    if observation_type == "public_tracking_identifier":
        return "tracking_markers"
    if observation_type == "public_download_destination":
        return "download_references"
    return "public_claims"


def _public_hostname(value: str) -> str:
    try:
        return (urlsplit(value).hostname or "").casefold().removeprefix("www.")
    except ValueError:
        return ""
