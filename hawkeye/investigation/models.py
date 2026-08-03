"""Event, assertion, review, lead, and progressive graph schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

EventKind = Literal[
    "run.started",
    "collection.started",
    "artifact.captured",
    "interactive_element.discovered",
    "evidence_gap.created",
    "agent.objective.created",
    "agent.fallback.activated",
    "tool.requested",
    "tool.blocked",
    "tool.completed",
    "observation.created",
    "entity.created",
    "entity.matched",
    "search.started",
    "search.lead.discovered",
    "candidate_page.selected",
    "candidate_page.approval_required",
    "candidate_page.approved",
    "candidate_page.collected",
    "candidate_page.collection_failed",
    "assertion.proposed",
    "review.required",
    "assertion.verified",
    "assertion.rejected",
    "assertion.needs_more_evidence",
    "assertion.duplicate",
    "assertion.uncertain",
    "run.completed",
    "run.failed",
]


class InvestigationEvent(BaseModel):
    event_id: str
    sequence: int = Field(ge=1)
    case_id: str
    run_id: str
    kind: EventKind
    occurred_at: datetime
    causation_event_id: str | None = None
    correlation_id: str
    schema_version: Literal["1.0"] = "1.0"
    payload: dict[str, Any]


class CandidateLead(BaseModel):
    lead_id: str
    case_id: str
    run_id: str
    url: str
    discovery_method: Literal["direct_link", "redirect", "new_tab", "iframe", "fixture_index"]
    source_observation_ids: list[str]
    collection_mode: Literal["synthetic_fixture", "real_world"]
    initial_status: Literal["waiting_for_approval", "approved_for_recollection"]
    created_at: datetime


class CandidateAssertion(BaseModel):
    assertion_id: str
    case_id: str
    run_id: str
    assertion_type: Literal[
        "publicly_links_to",
        "shares_public_contact_with",
        "shares_redirect_target_with",
        "shares_download_destination_with",
        "shares_referral_code_with",
        "claims_brand",
        "candidate_related_to",
    ]
    subject: str
    object: str
    supporting_observation_ids: list[str] = Field(min_length=1)
    source_artifact_ids: list[str] = Field(min_length=1)
    initial_status: Literal["needs_review"] = "needs_review"
    created_at: datetime
    limitations: list[str] = Field(default_factory=list)


class ReviewEvent(BaseModel):
    review_id: str
    assertion_id: str
    outcome: Literal["verified", "rejected", "needs_more_evidence", "duplicate", "uncertain"]
    reviewer_label: str
    occurred_at: datetime
    reason: str
    previous_version: int = Field(ge=0)
    new_version: int = Field(ge=1)


class ProgressiveGraphNode(BaseModel):
    id: str
    kind: Literal[
        "seed_page",
        "collected_page",
        "claimed_brand",
        "public_contact",
        "public_claim",
        "external_destination",
        "redirect_target",
        "candidate_domain",
    ]
    label: str
    status: Literal["observed", "lead", "collected", "verified", "rejected"]
    attributes: dict[str, Any] = Field(default_factory=dict)


class ProgressiveGraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation: str
    appearance: Literal["solid", "dashed", "solid_emphasized", "hidden"]
    supporting_event_ids: list[str]
    supporting_observation_ids: list[str] = Field(default_factory=list)


class GraphAnimation(BaseModel):
    sequence: int = Field(ge=1)
    animation: Literal["spawn-node", "draw-edge", "pulse-node", "focus-node"]
    target_id: str


class CausalLink(BaseModel):
    event_id: str
    causation_event_id: str | None


class ProgressiveGraphState(BaseModel):
    nodes: list[ProgressiveGraphNode]
    edges: list[ProgressiveGraphEdge]
    timeline: list[InvestigationEvent]
    causal_links: list[CausalLink]
    animations: list[GraphAnimation]
    applied_event_ids: list[str]
