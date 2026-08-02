"""Schemas for bounded, reproducible evaluation manifests and reports."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, model_validator

InvariantId = Literal[
    "navigation_attempted",
    "artifacts_preserved",
    "max_pages",
    "max_depth",
    "external_documents_crawled",
    "candidate_domains_crawled",
    "review_status",
]
InvariantOperator = Literal["equals", "less_or_equal"]
InvariantValue = bool | int | Literal["needs_review"]


class EvaluationCollectionPolicy(BaseModel):
    """The intentionally narrow collection envelope associated with one live manifest."""

    interactive: Literal[False]
    max_depth: int = Field(ge=0, le=1)
    max_pages: int = Field(ge=1, le=5)
    candidate_crawling: Literal[False]


class ExpectedInvariant(BaseModel):
    """A stable engine-behavior property, never a mutable live-site content assertion."""

    id: InvariantId
    operator: InvariantOperator
    value: InvariantValue

    @model_validator(mode="after")
    def validate_operator_and_value(self) -> ExpectedInvariant:
        numeric_ids = {
            "max_pages",
            "max_depth",
            "external_documents_crawled",
            "candidate_domains_crawled",
        }
        boolean_ids = {"navigation_attempted", "artifacts_preserved"}
        if self.id in numeric_ids:
            if self.operator not in {"equals", "less_or_equal"} or (
                not isinstance(self.value, int) or isinstance(self.value, bool)
            ):
                raise ValueError(f"Invariant {self.id} requires an integer value")
        elif self.id in boolean_ids:
            if self.operator != "equals" or not isinstance(self.value, bool):
                raise ValueError(f"Invariant {self.id} requires an equality boolean value")
        elif self.id == "review_status":
            if self.operator != "equals" or self.value != "needs_review":
                raise ValueError("review_status may only require needs_review")
        return self


class EvaluationManifest(BaseModel):
    """Checked-in definition for one opt-in public evaluation, not a live test fixture."""

    schema_version: Literal["1.0"] = "1.0"
    evaluation_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,79}$")
    input_url: str
    purpose: str = Field(min_length=1, max_length=500)
    source_type: Literal["public_web"]
    live_evaluation: Literal[True]
    collection_policy: EvaluationCollectionPolicy
    fixture_manifest_path: str
    fixture_manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    expected_invariants: list[ExpectedInvariant] = Field(min_length=1)
    environmental_restrictions: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_manifest(self) -> EvaluationManifest:
        parsed = urlsplit(self.input_url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
            raise ValueError("Evaluation input_url must be an absolute HTTP(S) URL")
        fixture_path = self.fixture_manifest_path.replace("\\", "/")
        if fixture_path.startswith("/") or ".." in fixture_path.split("/"):
            raise ValueError("fixture_manifest_path must be a repository-relative path")
        identifiers = [item.id for item in self.expected_invariants]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Each expected invariant may appear only once")
        return self


class InvariantResult(BaseModel):
    """One observed invariant result with the expected and actual values retained."""

    id: InvariantId
    operator: InvariantOperator
    expected: InvariantValue
    observed: InvariantValue
    passed: bool


class EvaluationReport(BaseModel):
    """Portable local-only assessment of a verified completed case against a manifest."""

    schema_version: Literal["1.0"] = "1.0"
    generated_at: datetime
    engine_version: str
    git_commit: str | None = None
    command: str
    evaluation_id: str
    manifest_path: str
    manifest_sha256: str
    fixture_manifest_path: str
    fixture_manifest_sha256: str
    input_url: str
    source_case_id: str
    source_case_manifest_sha256: str
    source_case_capture_outcome: str | None = None
    source_case_content_usable: bool | None = None
    artifact_sha256: dict[str, str]
    observed_invariants: list[InvariantResult]
    passed: bool
    environmental_restrictions: list[str]
