"""Portable schemas for G1 render-diagnostic artifacts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DiagnosticEvidenceReference(BaseModel):
    """A verified canonical evidence reference; diagnostics never replace it."""

    evidence_id: str
    type: Literal["html_page", "screenshot"]
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class RenderCheckpointMeasurement(BaseModel):
    """One fixed-time, non-interactive measurement of a separately loaded document."""

    elapsed_ms: int = Field(ge=0, le=3_000)
    document_ready_state: str
    html_bytes: int = Field(ge=0)
    visible_text_chars: int = Field(ge=0)
    element_count: int = Field(ge=0)
    anchor_count: int = Field(ge=0)
    image_count: int = Field(ge=0)
    iframe_count: int = Field(ge=0)
    canvas_count: int = Field(ge=0)
    document_height: int = Field(ge=0)
    screenshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    screenshot_bytes: int = Field(ge=0)
    screenshot_entropy: float = Field(ge=0.0)


class RenderCheckpointDelta(BaseModel):
    """A neutral difference between two adjacent fixed-time measurements."""

    from_elapsed_ms: int = Field(ge=0, le=3_000)
    to_elapsed_ms: int = Field(ge=0, le=3_000)
    html_bytes_delta: int
    visible_text_chars_delta: int
    element_count_delta: int
    anchor_count_delta: int
    image_count_delta: int
    iframe_count_delta: int
    canvas_count_delta: int
    document_height_delta: int
    screenshot_changed: bool
    screenshot_entropy_delta: float


class RenderDiagnosticsDocument(BaseModel):
    """One isolated G1 artifact that cannot affect the canonical V0–V1 case output."""

    schema_version: Literal["1.0"] = "1.0"
    measurement_method_version: Literal["render-diagnostics-1"] = "render-diagnostics-1"
    generated_at: datetime
    engine_version: str
    git_commit: str | None = None
    command: str
    collection_mode: Literal["fixture", "live"]
    source_case_id: str
    source_case_manifest_sha256: str
    source_page_id: str
    source_url: str
    source_evidence_refs: list[DiagnosticEvidenceReference]
    checkpoint_schedule_ms: list[int]
    diagnostic_wait_budget_ms: Literal[3000] = 3000
    total_diagnostic_time_ms: int = Field(ge=0)
    status: Literal[
        "stable_across_checkpoints",
        "changed_after_initial_capture",
        "continued_changing_at_budget_end",
        "low_information_across_checkpoints",
        "diagnostic_error",
    ]
    checkpoints: list[RenderCheckpointMeasurement] = Field(default_factory=list)
    deltas: list[RenderCheckpointDelta] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
