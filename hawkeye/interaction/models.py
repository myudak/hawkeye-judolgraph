"""Schemas for narrow read-only browser tools and their controlled fixture states."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class InteractionBudget(BaseModel):
    max_iterations: int = Field(default=5, ge=1, le=5)
    max_interactions: int = Field(default=3, ge=0, le=3)
    max_pages: int = Field(default=3, ge=1, le=3)
    max_depth: int = Field(default=1, ge=0, le=1)
    max_redirects: int = Field(default=5, ge=0, le=5)
    max_search_queries: int = Field(default=1, ge=0, le=1)
    max_candidate_pages: int = Field(default=3, ge=0, le=3)
    max_runtime_seconds: int = Field(default=120, ge=1, le=120)


class InteractiveElement(BaseModel):
    element_id: str
    dom_path: str
    role: str
    tag: str
    accessible_name: str
    visible_text: str
    href: str | None = None
    action: str | None = None
    form_owner: str | None = None
    form_action: str | None = None
    download_attribute: bool = False
    opens_new_tab: bool = False
    declared_behavior: Literal[
        "reveal_modal",
        "reveal_menu",
        "reveal_tab",
        "inspect_public_iframe",
        "open_public_link",
        "none",
    ] = "none"
    reveals_observations: list[str] = Field(default_factory=list)
    destination_url: str | None = None
    expected_unsafe: bool = False
    available_after: list[str] = Field(default_factory=list)


class StableElementReference(BaseModel):
    reference_id: str
    discovery_snapshot_id: str
    element_id: str
    dom_path: str
    role: str
    tag: str
    accessible_name: str
    visible_text: str
    href: str | None = None
    action: str | None = None
    element_fingerprint: str


class ControlledScenario(BaseModel):
    scenario_id: str
    ordinal: int = Field(ge=1, le=10)
    name: str
    seed_url: str
    initial_observations: list[str] = Field(default_factory=list)
    expected_observable: str | None = None
    required_interaction: str | None = None
    expected_candidate: str | None = None
    expected_relation: str | None = None
    elements: list[InteractiveElement] = Field(default_factory=list)
    redirect_chain: list[str] = Field(default_factory=list)
    unsafe_control_ids: list[str] = Field(default_factory=list)


class InteractionDecision(BaseModel):
    status: Literal["completed", "blocked", "stale_reference", "budget_exhausted"]
    tool_name: Literal[
        "page_get_state",
        "page_list_interactive_elements",
        "page_click_read_only",
        "page_open_public_link",
        "page_capture_state",
        "page_get_redirect_chain",
    ]
    reason: str
    snapshot_id: str
    observations: list[str] = Field(default_factory=list)
    destination_url: str | None = None
    policy_checks: dict[str, str | bool | int | None] = Field(default_factory=dict)
    before_snapshot_id: str | None = None
    added_observations: list[str] = Field(default_factory=list)
    removed_observations: list[str] = Field(default_factory=list)
    state_changed: bool = False


class ControlledPageState(BaseModel):
    scenario_id: str
    url: str
    snapshot_id: str
    observations: list[str]
    interaction_count: int = Field(ge=0)
    page_count: int = Field(ge=1)
    redirect_chain: list[str]
    available_element_ids: list[str] = Field(default_factory=list)
