"""Idempotent event reducer for stable graph truth and a separate animation queue."""

from __future__ import annotations

from typing import Literal

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
            node_id = str(payload.get("node_id", f"page:{event.sequence}"))
            nodes[node_id] = ProgressiveGraphNode(
                id=node_id,
                kind="collected_page",
                label=str(payload.get("label", node_id)),
                status="collected",
                attributes=payload,
            )
            animations.append(
                GraphAnimation(sequence=event.sequence, animation="spawn-node", target_id=node_id)
            )
        elif event.kind == "observation.created":
            node_id = str(payload.get("node_id", f"observation:{event.sequence}"))
            observation_type = str(payload.get("observation_type", "public_contact"))
            kind: Literal["claimed_brand", "public_contact"] = (
                "claimed_brand"
                if observation_type == "claimed_brand_identity"
                else "public_contact"
            )
            nodes[node_id] = ProgressiveGraphNode(
                id=node_id,
                kind=kind,
                label=str(payload.get("normalized_value", node_id)),
                status="observed",
                attributes=payload,
            )
            source = str(payload.get("source_node_id", f"seed:{event.case_id}"))
            edge_id = f"observed:{source}:{node_id}"
            edges[edge_id] = ProgressiveGraphEdge(
                id=edge_id,
                source=source,
                target=node_id,
                relation="observed",
                appearance="solid",
                supporting_event_ids=[event.event_id],
                supporting_observation_ids=[str(payload.get("observation_id", ""))],
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
            node_id = f"candidate:{payload.get('lead_id', event.sequence)}"
            nodes[node_id] = ProgressiveGraphNode(
                id=node_id,
                kind="candidate_domain",
                label=str(payload.get("url", node_id)),
                status="lead",
                attributes=payload,
            )
            animations.append(
                GraphAnimation(sequence=event.sequence, animation="spawn-node", target_id=node_id)
            )
        elif event.kind == "candidate_page.collected":
            node_id = str(payload.get("node_id", f"candidate-page:{event.sequence}"))
            nodes[node_id] = ProgressiveGraphNode(
                id=node_id,
                kind="collected_page",
                label=str(payload.get("url", node_id)),
                status="collected",
                attributes=payload,
            )
            animations.append(
                GraphAnimation(sequence=event.sequence, animation="spawn-node", target_id=node_id)
            )
        elif event.kind == "assertion.proposed":
            assertion_id = str(payload["assertion_id"])
            source = str(payload.get("subject_node_id", f"seed:{event.case_id}"))
            target = str(payload.get("object_node_id", f"candidate-page:{event.sequence}"))
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
