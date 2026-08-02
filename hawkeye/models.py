"""Pydantic schemas used by the Engine V0 evidence pipeline."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class CaptureOutcome(StrEnum):
    """Deterministic classification of the document captured by a completed navigation."""

    CONTENT = "content"
    UNAVAILABLE_PAGE = "unavailable_page"
    BOT_CHALLENGE = "bot_challenge"
    GEO_RESTRICTED = "geo_restricted"
    CONSENT_WALL = "consent_wall"
    NAVIGATION_ERROR = "navigation_error"
    TIMEOUT = "timeout"
    UNKNOWN_RESTRICTION = "unknown_restriction"


class CaptureClassification(BaseModel):
    """Stable, explainable outcome assessment for one page capture."""

    outcome: CaptureOutcome
    content_usable: bool
    reasons: list[str] = Field(default_factory=list)


class RedirectRecord(BaseModel):
    """One observed redirect hop, retaining a status code when Playwright exposes it."""

    source_url: str
    destination_url: str
    status_code: int | None = Field(default=None, ge=100, le=599)
    raw_location: str | None = None
    resource_type: str = "document"
    is_top_level_navigation: bool = True


class BlockedRequestRecord(BaseModel):
    """A browser request refused before it could reach an unsafe destination."""

    url: str
    resource_type: str
    reason: str
    is_navigation: bool = False


class CrawlConfiguration(BaseModel):
    """Hard, auditable limits for the bounded V0.1 same-site crawler."""

    max_depth: int = Field(ge=0, le=1)
    max_pages_total: int = Field(ge=1, le=5)
    max_redirects_per_page: int = Field(ge=0, le=5)
    page_timeout_seconds: float = Field(gt=0, le=30)
    case_timeout_seconds: float = Field(gt=0, le=120)
    max_html_bytes: int = Field(gt=0)
    max_total_requests: int = Field(gt=0)
    max_declared_response_bytes: int = Field(gt=0)
    allowed_crawl_hosts: list[str] = Field(default_factory=list)


class CrawlPageRecord(BaseModel):
    """One bounded crawl target and its independently auditable capture result."""

    id: str
    url: str
    normalized_url: str
    depth: int = Field(ge=0)
    state: Literal["discovered", "queued", "visiting", "completed", "skipped", "failed"]
    parent_page_id: str | None = None
    source_evidence_id: str | None = None
    original_href: str | None = None
    discovery_method: Literal["seed", "html_anchor"] = "seed"
    anchor_text: str | None = None
    final_url: str | None = None
    redirects: list[RedirectRecord] = Field(default_factory=list)
    navigation_status: Literal["pending", "captured", "failed", "timed_out"] = "pending"
    capture_outcome: CaptureOutcome | None = None
    content_usable: bool | None = None
    classification_reasons: list[str] = Field(default_factory=list)
    page_title: str | None = None
    html_evidence_id: str | None = None
    screenshot_evidence_id: str | None = None
    redirect_evidence_id: str | None = None
    content_sha256: str | None = None
    content_type: str | None = None
    blocked_requests: list[BlockedRequestRecord] = Field(default_factory=list)
    blocked_popup_count: int = Field(default=0, ge=0)
    blocked_download_count: int = Field(default=0, ge=0)
    duplicate_of_page_id: str | None = None
    skip_reason: str | None = None
    error: str | None = None


class CrawlFrontierRecord(BaseModel):
    """An observed link's deterministic frontier state, including skip decisions."""

    id: str
    depth: int = Field(ge=0)
    state: Literal["discovered", "queued", "visiting", "completed", "skipped", "failed"]
    original_href: str | None = None
    normalized_url: str | None = None
    source_page_id: str | None = None
    source_evidence_id: str | None = None
    discovery_method: Literal["seed", "html_anchor", "redirect"] = "seed"
    anchor_text: str | None = None
    target_page_id: str | None = None
    skip_reason: str | None = None
    redirect_status_code: int | None = Field(default=None, ge=100, le=599)


class CandidateObservation(BaseModel):
    """An immutable observed fact considered by deterministic candidate generation."""

    id: str
    observation_type: Literal[
        "external_link",
        "external_redirect",
        "external_discovery",
        "signal",
    ]
    source_case_id: str
    source_page_id: str | None = None
    source_evidence_id: str | None = None
    source_url: str
    target_url: str | None = None
    target_host: str | None = None
    signal_type: str | None = None
    signal_value: str | None = None
    direction: Literal["source_to_candidate", "undirected"]
    discovery_method: Literal[
        "html_anchor",
        "network_redirect",
        "public_source",
        "local_corpus_match",
    ]
    candidate_decision: Literal["accepted", "excluded"]
    exclusion_reason: str | None = None
    details: dict[str, str] = Field(default_factory=dict)


class CandidateEvidenceReference(BaseModel):
    """A globally unambiguous reference to one source-case evidence observation."""

    case_id: str
    evidence_id: str
    observation_id: str


class CandidateReason(BaseModel):
    """A derived, relationship-neutral reason to prioritize a pending candidate."""

    reason_type: Literal[
        "external_link",
        "external_redirect",
        "external_discovery",
        "shared_telegram",
        "shared_whatsapp_or_phone",
        "shared_referral",
        "shared_exact_asset_url",
    ]
    signal_value: str | None = None
    weight: int = Field(ge=0, le=100)
    signal_quality: Literal["observed", "strong", "medium", "weak"]
    corpus_frequency: int = Field(ge=0)
    corpus_case_count: int = Field(ge=0)
    corpus_domain_count: int = Field(ge=0)
    source_case_ids: list[str]
    source_urls: list[str]
    supporting_evidence_ids: list[str]
    supporting_evidence_refs: list[CandidateEvidenceReference]
    source_observation_ids: list[str]
    direction: Literal["source_to_candidate", "undirected"]
    discovery_method: Literal[
        "html_anchor",
        "network_redirect",
        "public_source",
        "local_corpus_match",
    ]


class CandidateRecord(BaseModel):
    """One pending candidate domain, not a relationship conclusion or crawl instruction."""

    candidate_id: str
    hostname: str
    registrable_domain: str
    suffix_type: Literal["icann", "private"]
    scope_relation: Literal[
        "different_registrable_domain",
        "same_registrable_domain_external_host",
    ]
    observed_hosts: list[str]
    status: Literal["pending"] = "pending"
    relationship: None = None
    discovery_priority_score: int = Field(ge=0, le=100)
    reasons: list[CandidateReason]


class CandidateCorpusExclusion(BaseModel):
    """A local corpus entry deliberately ignored, with an auditable reason."""

    directory_name: str
    case_id: str | None = None
    reason: str


class CandidateCorpusSnapshot(BaseModel):
    """The local completed-case corpus snapshot used for a candidate run."""

    case_ids: list[str]
    case_count: int = Field(ge=0)
    manifest_sha256: str
    generated_at: datetime
    excluded_cases: list[CandidateCorpusExclusion] = Field(default_factory=list)


class CandidateDocument(BaseModel):
    """Portable V0.2 candidate output derived only from saved case evidence and corpus facts."""

    schema_version: Literal["0.2.0"] = "0.2.0"
    scoring_policy_version: Literal["v0.2-host-priority-1"] = "v0.2-host-priority-1"
    source_case_id: str
    candidates: list[CandidateRecord]
    excluded_observation_count: int = Field(ge=0)
    corpus: CandidateCorpusSnapshot


class ComparisonEvidenceReference(BaseModel):
    """A verified local artifact used by one offline comparison component."""

    case_id: str
    evidence_id: str
    path: str
    sha256: str


class ComparisonEntityReference(BaseModel):
    """An evidence-linked extracted entity contributing to a comparison component."""

    case_id: str
    entity_id: str
    evidence_id: str
    type: str
    normalized_value: str


class ComparisonComponent(BaseModel):
    """One separately explainable V0.3 similarity component."""

    name: Literal[
        "shared_entity_similarity",
        "visible_text_similarity",
        "dom_structure_similarity",
        "screenshot_perceptual_similarity",
        "shared_asset_similarity",
    ]
    score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(gt=0.0, le=1.0)
    available: bool
    status: Literal["scored", "not_applicable", "low_information"]
    evidence_refs: list[ComparisonEvidenceReference] = Field(default_factory=list)
    entity_refs: list[ComparisonEntityReference] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class ComparisonDocument(BaseModel):
    """Portable offline domain-comparison output; it is not an ownership conclusion."""

    schema_version: Literal["0.3.0"] = "0.3.0"
    comparator_version: Literal["0.3.0"] = "0.3.0"
    scoring_policy_version: Literal["v0.3-offline-comparison-1"] = "v0.3-offline-comparison-1"
    left_case_id: str
    right_case_id: str
    left_final_url: str | None = None
    right_final_url: str | None = None
    left_case_manifest_sha256: str
    right_case_manifest_sha256: str
    weights: dict[str, float]
    review_status: Literal["needs_review"] = "needs_review"
    candidate_mirror_score: float = Field(ge=0.0, le=100.0)
    components: list[ComparisonComponent]
    warnings: list[str] = Field(default_factory=list)
    generated_at: datetime


class ExternalDiscoveryEvidenceReference(BaseModel):
    """One immutable raw response artifact from an isolated V0.4 public source."""

    id: str
    source_name: Literal["urlscan_public"]
    request_url: str
    path: str
    metadata_path: str
    sha256: str
    collected_at: datetime
    collection_mode: Literal["live", "fixture_replay"]
    http_status: int | None = Field(default=None, ge=100, le=599)
    content_type: Literal["application/json"] = "application/json"
    response_bytes: int = Field(ge=0)
    result_limit: int = Field(ge=1, le=20)


class ExternalDiscoveryObservation(BaseModel):
    """A single URL field observed in one public-source result, before interpretation."""

    id: str
    source_name: Literal["urlscan_public"]
    source_result_id: str
    source_field: Literal["task_url", "page_url"]
    observed_url: str
    target_host: str | None = None
    candidate_decision: Literal["accepted", "excluded"]
    exclusion_reason: str | None = None
    evidence_id: str
    candidate_observation_id: str


class ExternalDiscoveryDocument(BaseModel):
    """Auditable output from exactly one bounded external-discovery source run."""

    schema_version: Literal["0.4.0"] = "0.4.0"
    source_name: Literal["urlscan_public"]
    source_version: Literal["urlscan-public-search-1"] = "urlscan-public-search-1"
    source_case_id: str
    source_case_json_sha256: str
    query_hostname: str
    source_result_count: int = Field(ge=0)
    response_evidence: ExternalDiscoveryEvidenceReference
    candidates: list[CandidateRecord]
    observations: list[ExternalDiscoveryObservation]
    candidate_document_path: str
    candidate_observations_path: str
    excluded_observation_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
    generated_at: datetime


class CaseRecord(BaseModel):
    """Persisted state for one bounded seed investigation."""

    case_id: str
    seed_url: str
    status: Literal["running", "completed", "failed"]
    started_at: datetime
    completed_at: datetime | None = None
    final_url: str | None = None
    redirect_chain: list[str] = Field(default_factory=list)
    redirects: list[RedirectRecord] = Field(default_factory=list)
    navigation_status: Literal["pending", "captured", "failed", "timed_out"] = "pending"
    capture_outcome: CaptureOutcome | None = None
    content_usable: bool | None = None
    classification_reasons: list[str] = Field(default_factory=list)
    page_title: str | None = None
    page_count: int = 0
    crawl_configuration: CrawlConfiguration | None = None
    allowed_crawl_hosts: list[str] = Field(default_factory=list)
    total_request_count: int = Field(default=0, ge=0)
    total_declared_response_bytes: int = Field(default=0, ge=0)
    budget_exhausted_reason: str | None = None
    candidate_count: int = Field(default=0, ge=0)
    error: str | None = None


class EvidenceRecord(BaseModel):
    """An immutable local artifact record and its integrity data."""

    id: str
    type: Literal["html_page", "screenshot", "network_event"]
    source_url: str
    path: str
    collected_at: datetime
    sha256: str
    page_id: str | None = None
    viewport: dict[str, int] | None = None
    image_dimensions: dict[str, int] | None = None


class ExtractedEntity(BaseModel):
    """A deterministic signal derived from one saved HTML evidence artifact."""

    id: str
    type: str
    value: str
    normalized_value: str
    source_evidence_id: str
    source_url: str
    extraction_method: str
    confidence: float = Field(ge=0.0, le=1.0)
    details: dict[str, str] = Field(default_factory=dict)


class GraphNode(BaseModel):
    """A graph node representing a case, public resource, or extracted signal."""

    id: str
    type: Literal[
        "case",
        "domain",
        "page",
        "screenshot",
        "telegram",
        "whatsapp_or_phone",
        "referral",
        "external_asset_domain",
        "external_asset_url",
    ]
    label: str
    attributes: dict[str, Any] = Field(default_factory=dict)


STRUCTURAL_EDGE_TYPES = {"started_from", "resolved_to", "contains_page", "captured_as"}


class GraphEdge(BaseModel):
    """A directed graph relationship with evidence for extracted facts."""

    id: str
    source: str
    target: str
    type: Literal[
        "started_from",
        "resolved_to",
        "contains_page",
        "captured_as",
        "discovered_via_link",
        "links_to",
        "mentions",
        "uses_referral",
        "loads_asset_from",
    ]
    evidence_id: str | None = None
    source_url: str | None = None
    extraction_method: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_evidence_for_extracted_edge(self) -> GraphEdge:
        if self.type not in STRUCTURAL_EDGE_TYPES:
            missing = [
                name
                for name, value in (
                    ("evidence_id", self.evidence_id),
                    ("source_url", self.source_url),
                    ("extraction_method", self.extraction_method),
                    ("confidence", self.confidence),
                )
                if value is None
            ]
            if missing:
                joined = ", ".join(missing)
                raise ValueError(f"Extracted graph edge requires evidence fields: {joined}")
        return self


class GraphDocument(BaseModel):
    """Portable graph output for a single case."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    metadata: dict[str, Any]


class CollectedPage(BaseModel):
    """Ephemeral result returned by the Playwright collector before storage."""

    final_url: str
    redirect_chain: list[str]
    redirects: list[RedirectRecord]
    title: str
    html: str
    screenshot: bytes
    viewport: dict[str, int]
    image_dimensions: dict[str, int]
    collected_at: datetime
    content_type: str = "text/html"
    blocked_requests: list[BlockedRequestRecord] = Field(default_factory=list)
    blocked_popup_count: int = Field(default=0, ge=0)
    blocked_download_count: int = Field(default=0, ge=0)


class InvestigationResult(BaseModel):
    """Small programmatic and CLI-facing investigation summary."""

    case_directory: str
    case: CaseRecord
    pages: list[CrawlPageRecord] = Field(default_factory=list)
    frontier: list[CrawlFrontierRecord] = Field(default_factory=list)
    candidates: list[CandidateRecord] = Field(default_factory=list)
