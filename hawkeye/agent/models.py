"""Validated schemas for Codex capability diagnostics and investigator decisions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hawkeye.interaction.models import (
    InteractionBudget,
    InteractionDecision,
    StableElementReference,
)


class EndpointCapability(BaseModel):
    endpoint: str
    reachable: bool
    http_status: int | None = Field(default=None, ge=100, le=599)
    route_supported: bool | None = None
    available_model: str | None = None
    streaming_support: bool | None = None
    structured_output_support: bool | None = None
    function_call_support: bool | None = None
    tool_result_continuation: bool | None = None
    cancellation_support: bool | None = None
    timeout_behavior: Literal["bounded", "unbounded", "unknown"] = "unknown"
    native_search_support: Literal[
        "supported_structured", "supported_unstructured", "unsupported", "unknown"
    ] = "unknown"
    native_search_source_url_visibility: bool | None = None
    response_content_type: str | None = None
    latency_ms: int = Field(ge=0)
    diagnostic: str


class CapabilityDiagnostics(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    generated_at: datetime
    endpoints: list[EndpointCapability]
    supported_route: str | None = None
    selected_model: str | None = None
    safe_to_enable_model_path: bool = False
    fallback_required: bool
    secrets_persisted: Literal[False] = False


class AgentVisibleContext(BaseModel):
    """The complete bounded context made visible to either investigator implementation."""

    objective: str = Field(max_length=1000)
    current_case_state: dict[str, str | int | bool | None]
    normalized_observations: list[str] = Field(max_length=500)
    safe_interactive_elements: list[StableElementReference] = Field(max_length=100)
    policy_budget: InteractionBudget
    prior_tool_results: list[InteractionDecision] = Field(default_factory=list, max_length=10)
    evidence_gap: str = Field(max_length=1000)


class AgentDecision(BaseModel):
    """Strict decision schema; free-form tool-call parsing is never accepted."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["tool_request", "assertion_proposal", "stop"]
    tool_name: (
        Literal[
            "page_get_state",
            "page_list_interactive_elements",
            "page_click_read_only",
            "page_open_public_link",
            "page_capture_state",
            "page_get_redirect_chain",
        ]
        | None
    ) = None
    element_reference: StableElementReference | None = None
    assertion_type: (
        Literal[
            "publicly_links_to",
            "shares_public_contact_with",
            "shares_redirect_target_with",
            "shares_download_destination_with",
            "shares_referral_code_with",
            "claims_brand",
            "candidate_related_to",
        ]
        | None
    ) = None
    assertion_subject: str | None = Field(default=None, max_length=2000)
    assertion_object: str | None = Field(default=None, max_length=2000)
    supporting_observation_ids: list[str] = Field(default_factory=list, max_length=50)
    outcome_summary: str = Field(max_length=1000)

    @model_validator(mode="after")
    def validate_action_shape(self) -> AgentDecision:
        if self.action == "tool_request" and self.tool_name is None:
            raise ValueError("tool_request requires tool_name")
        if self.action == "assertion_proposal" and (
            self.assertion_type is None
            or self.assertion_subject is None
            or self.assertion_object is None
            or not self.supporting_observation_ids
        ):
            raise ValueError("assertion_proposal requires type, endpoints, and evidence IDs")
        return self


class AgentFailure(BaseModel):
    attempt: int = Field(ge=1, le=2)
    category: Literal["endpoint_unavailable", "invalid_schema", "transport_error"]
    message: str = Field(max_length=1000)
    fallback_activated: bool


class AgentStepResult(BaseModel):
    decision: AgentDecision
    mode: Literal["codex", "deterministic_fallback"]
    failures: list[AgentFailure] = Field(default_factory=list)
    raw_response_persisted: Literal[False] = False
    metadata: dict[str, Any] = Field(default_factory=dict)
