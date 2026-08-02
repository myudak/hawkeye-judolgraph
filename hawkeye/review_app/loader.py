"""Fail-closed local case loader and safe display projection for the V1 review console."""

from __future__ import annotations

import hashlib
import json
import os
import re
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qsl, quote, urlsplit, urlunsplit

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel

from hawkeye.diagnostics.models import RenderDiagnosticsDocument
from hawkeye.models import (
    CandidateDocument,
    CandidateObservation,
    CaseRecord,
    ComparisonDocument,
    CrawlPageRecord,
    EvidenceRecord,
    ExtractedEntity,
    GraphDocument,
    SemanticObservation,
)

_CASE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
_SENSITIVE_QUERY_KEY_RE = re.compile(
    r"(?:api[-_]?key|auth(?:orization)?|code|credential|pass(?:word)?|secret|session|sid|token)",
    re.IGNORECASE,
)
_MAX_CASE_JSON_BYTES = 2_000_000
_MAX_HTML_BYTES = 5_000_000
_MAX_TEXT_BYTES = 5_000_000
_MAX_SCREENSHOT_BYTES = 10_000_000
_MAX_NETWORK_BYTES = 1_000_000
_MAX_SCREENSHOT_PIXELS = 25_000_000
_MAX_COMPARISON_BYTES = 2_000_000
_DIAGNOSTIC_WARNING = (
    "A render diagnostic artifact is present but cannot be verified against this local case."
)


class CaseNotFoundError(KeyError):
    """Raised when a requested opaque case ID is not an immediate child of the configured root."""


class CaseIntegrityError(ValueError):
    """Raised when a persisted case fails V1's evidence and containment checks."""


@dataclass(frozen=True)
class LoadedCase:
    """The fully integrity-checked local inputs that may be exposed through the review API."""

    directory: Path
    case: CaseRecord
    pages: list[CrawlPageRecord]
    evidence_by_id: dict[str, EvidenceRecord]
    entities: list[ExtractedEntity]
    observations: list[SemanticObservation]
    candidates: CandidateDocument | None
    candidate_observations: list[CandidateObservation]
    graph: GraphDocument | None
    manifest_sha256: str
    diagnostics: RenderDiagnosticsDocument | None
    diagnostic_warning: str | None


@dataclass(frozen=True)
class ArtifactPayload:
    """A verified artifact body plus the one safe response representation for its known type."""

    content: bytes
    media_type: str
    disposition: str


class CaseLoader:
    """Resolve case and artifact IDs through verified manifests only; never accept paths."""

    def __init__(
        self, cases_root: Path | str, *, comparisons_root: Path | str | None = None
    ) -> None:
        requested_root = Path(cases_root).expanduser()
        if _is_reparse_point(requested_root):
            raise CaseIntegrityError("Configured cases root must not be a reparse point")
        try:
            root = requested_root.resolve()
        except OSError as error:
            raise CaseIntegrityError("Unable to resolve configured cases root") from error
        if not root.is_dir():
            raise CaseIntegrityError("Configured cases root does not exist or is not a directory")
        self._root = root
        self._comparisons_root = self._resolve_comparisons_root(comparisons_root)

    def list_cases(self) -> list[dict[str, Any]]:
        """List immediate case directories, marking corrupt packages without exposing contents."""

        try:
            directories = sorted(self._root.iterdir(), key=lambda path: path.name)
        except OSError as error:
            raise CaseIntegrityError("Unable to enumerate configured cases root") from error
        summaries: list[dict[str, Any]] = []
        for directory in directories:
            if (
                not _CASE_ID_RE.fullmatch(directory.name)
                or _is_reparse_point(directory)
                or not directory.is_dir()
            ):
                continue
            try:
                summaries.append(case_summary(self.load(directory.name)))
            except CaseIntegrityError:
                summaries.append(
                    {
                        "case_id": directory.name,
                        "integrity": "error",
                        "error": "case integrity verification failed",
                    }
                )
        return summaries

    def load(self, case_id: str) -> LoadedCase:
        """Parse and verify all material before handing any case facts to the API or UI."""

        directory = self._case_directory(case_id)
        try:
            case = CaseRecord.model_validate(_read_json(directory, "case.json"))
            pages = _models_from_json(directory, "pages.json", CrawlPageRecord)
            evidence = _models_from_json(directory, "evidence.json", EvidenceRecord)
            entities = _models_from_json(directory, "entities.json", ExtractedEntity)
            observations = (
                _models_from_json(directory, "observations.json", SemanticObservation)
                if _file_exists(directory, "observations.json")
                else []
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise CaseIntegrityError("Case core JSON cannot be validated") from error
        if case.case_id != case_id:
            raise CaseIntegrityError("Case directory and case ID do not match")
        if case.status != "completed":
            raise CaseIntegrityError("Only completed cases can be reviewed")
        evidence_by_id = _index_unique(evidence, "evidence")
        _index_unique(pages, "page")
        _index_unique(entities, "entity")
        _validate_page_and_entity_references(pages, evidence_by_id, entities)
        _validate_semantic_observation_references(observations, evidence_by_id)
        _verify_all_evidence_artifacts(directory, evidence)
        graph = _load_graph(directory, evidence_by_id)
        candidates, candidate_observations = _load_candidates(directory, case, evidence_by_id)
        manifest_sha256 = _case_manifest(case, pages, evidence, entities)
        diagnostics, diagnostic_warning = _load_diagnostics(
            directory,
            case_id=case.case_id,
            manifest_sha256=manifest_sha256,
            pages=pages,
            evidence_by_id=evidence_by_id,
        )
        return LoadedCase(
            directory=directory,
            case=case,
            pages=sorted(pages, key=lambda page: page.id),
            evidence_by_id=evidence_by_id,
            entities=sorted(entities, key=lambda entity: entity.id),
            observations=sorted(observations, key=lambda item: item.id),
            candidates=candidates,
            candidate_observations=sorted(candidate_observations, key=lambda item: item.id),
            graph=graph,
            manifest_sha256=manifest_sha256,
            diagnostics=diagnostics,
            diagnostic_warning=diagnostic_warning,
        )

    def artifact(self, case_id: str, evidence_id: str) -> ArtifactPayload:
        """Serve one evidence ID after a fresh full-case verification, never an arbitrary path."""

        loaded = self.load(case_id)
        record = loaded.evidence_by_id.get(evidence_id)
        if record is None:
            raise CaseNotFoundError("Evidence ID was not found in the verified case manifest")
        content = _read_verified_artifact(loaded.directory, record)
        media_type, disposition = _artifact_response_policy(record)
        return ArtifactPayload(content=content, media_type=media_type, disposition=disposition)

    def _case_directory(self, case_id: str) -> Path:
        if not _CASE_ID_RE.fullmatch(case_id):
            raise CaseNotFoundError("Case ID was not found")
        candidate = self._root / case_id
        if _is_reparse_point(candidate) or not candidate.is_dir():
            raise CaseNotFoundError("Case ID was not found")
        try:
            resolved = candidate.resolve()
        except OSError as error:
            raise CaseNotFoundError("Case ID was not found") from error
        if resolved == self._root or self._root not in resolved.parents:
            raise CaseNotFoundError("Case ID was not found")
        return resolved

    def comparisons_for_case(self, loaded: LoadedCase) -> tuple[list[ComparisonDocument], bool]:
        """Return only comparison documents whose persisted inputs still verify locally.

        Comparisons are optional display companions kept in a separately configured directory. They
        never change a case package, and an invalid companion produces a visible warning instead of
        becoming a comparison fact.
        """

        if self._comparisons_root is None:
            return [], False
        try:
            paths = sorted(self._comparisons_root.iterdir(), key=lambda path: path.name)
        except OSError as error:
            raise CaseIntegrityError("Unable to enumerate configured comparison root") from error

        documents: list[ComparisonDocument] = []
        warning = False
        for path in paths:
            if path.suffix.casefold() != ".json":
                continue
            if _is_reparse_point(path) or not path.is_file():
                warning = True
                continue
            try:
                document = _read_comparison_document(path)
            except (CaseIntegrityError, OSError, TypeError, ValueError, json.JSONDecodeError):
                warning = True
                continue
            if loaded.case.case_id not in {document.left_case_id, document.right_case_id}:
                continue
            try:
                self._verify_comparison_document(document)
            except CaseIntegrityError:
                warning = True
                continue
            documents.append(document)
        return documents, warning

    def _resolve_comparisons_root(self, comparisons_root: Path | str | None) -> Path | None:
        if comparisons_root is None:
            return None
        requested_root = Path(comparisons_root).expanduser()
        if _is_reparse_point(requested_root):
            raise CaseIntegrityError("Configured comparison root must not be a reparse point")
        try:
            root = requested_root.resolve()
        except OSError as error:
            raise CaseIntegrityError("Unable to resolve configured comparison root") from error
        if not root.is_dir() or root == self._root:
            raise CaseIntegrityError(
                "Configured comparison root must be a separate existing directory"
            )
        return root

    def _verify_comparison_document(self, document: ComparisonDocument) -> None:
        if document.left_case_id == document.right_case_id:
            raise CaseIntegrityError("Comparison document must name two distinct cases")
        try:
            left = self.load(document.left_case_id)
            right = self.load(document.right_case_id)
        except CaseNotFoundError as error:
            raise CaseIntegrityError("Comparison references a case outside this console") from error
        if (
            document.left_case_manifest_sha256 != left.manifest_sha256
            or document.right_case_manifest_sha256 != right.manifest_sha256
        ):
            raise CaseIntegrityError("Comparison manifest references do not match verified cases")
        cases = {left.case.case_id: left, right.case.case_id: right}
        entities = {
            case_id: {entity.id: entity for entity in case.entities}
            for case_id, case in cases.items()
        }
        for component in document.components:
            for reference in component.evidence_refs:
                source_case = cases.get(reference.case_id)
                if source_case is None:
                    raise CaseIntegrityError(
                        "Comparison evidence reference is outside its case pair"
                    )
                evidence = source_case.evidence_by_id.get(reference.evidence_id)
                if (
                    evidence is None
                    or evidence.path != reference.path
                    or evidence.sha256 != reference.sha256
                ):
                    raise CaseIntegrityError("Comparison evidence reference cannot be verified")
            for entity_reference in component.entity_refs:
                source_case = cases.get(entity_reference.case_id)
                entity = entities.get(entity_reference.case_id, {}).get(entity_reference.entity_id)
                if (
                    source_case is None
                    or entity is None
                    or entity.source_evidence_id != entity_reference.evidence_id
                    or entity.type != entity_reference.type
                    or entity.normalized_value != entity_reference.normalized_value
                    or entity_reference.evidence_id not in source_case.evidence_by_id
                ):
                    raise CaseIntegrityError("Comparison entity reference cannot be verified")


def case_summary(loaded: LoadedCase) -> dict[str, Any]:
    """Return only safe, display-ready case facts; raw stored URLs never become application HTML."""

    return {
        "case_id": loaded.case.case_id,
        "integrity": "verified",
        "status": loaded.case.status,
        "final_url_display": safe_display_url(loaded.case.final_url),
        "capture_outcome": (
            loaded.case.capture_outcome.value if loaded.case.capture_outcome is not None else None
        ),
        "content_usable": loaded.case.content_usable,
        "access_outcome": (
            loaded.case.access_outcome.value if loaded.case.access_outcome is not None else None
        ),
        "capture_adequacy": (
            loaded.case.capture_adequacy.value if loaded.case.capture_adequacy is not None else None
        ),
        "extraction_eligible": loaded.case.extraction_eligible,
        "public_status": (
            loaded.case.public_status.value if loaded.case.public_status is not None else None
        ),
        "page_count": loaded.case.page_count,
        "candidate_count": loaded.case.candidate_count,
        "case_manifest_sha256": loaded.manifest_sha256,
    }


def case_details(
    loaded: LoadedCase,
    *,
    comparisons: list[ComparisonDocument] | None = None,
    comparison_integrity_warning: bool = False,
) -> dict[str, Any]:
    """Project a verified package into a UI-safe, relationship-neutral review model."""

    evidence_ids = set(loaded.evidence_by_id)
    graph_nodes = {node.id: node for node in loaded.graph.nodes} if loaded.graph else {}
    summary = case_summary(loaded)
    summary.update(
        {
            "seed_url_display": safe_display_url(loaded.case.seed_url),
            "navigation_status": loaded.case.navigation_status,
            "classification_reasons": [
                _safe_text(reason, 256) for reason in loaded.case.classification_reasons
            ],
            "collection_limits": _display_collection_limits(loaded.case),
            "pages": [
                {
                    "id": page.id,
                    "depth": page.depth,
                    "state": page.state,
                    "final_url_display": safe_display_url(page.final_url or page.normalized_url),
                    "capture_outcome": (
                        page.capture_outcome.value if page.capture_outcome is not None else None
                    ),
                    "content_usable": page.content_usable,
                    "access_outcome": (
                        page.access_outcome.value if page.access_outcome is not None else None
                    ),
                    "capture_adequacy": (
                        page.capture_adequacy.value if page.capture_adequacy is not None else None
                    ),
                    "extraction_eligible": page.extraction_eligible,
                    "extraction_skip_reason": page.extraction_skip_reason,
                    "public_status": (
                        page.public_status.value if page.public_status is not None else None
                    ),
                    "limitation_reasons": [
                        _safe_text(reason, 256) for reason in page.limitation_reasons
                    ],
                    "html_evidence_id": page.html_evidence_id,
                    "screenshot_evidence_id": page.screenshot_evidence_id,
                    "initial_screenshot_evidence_id": page.initial_screenshot_evidence_id,
                    "full_page_screenshot_evidence_id": page.full_page_screenshot_evidence_id,
                    "visible_text_evidence_id": page.visible_text_evidence_id,
                    "readiness_evidence_id": page.readiness_evidence_id,
                    "classification_reasons": [
                        _safe_text(reason, 256) for reason in page.classification_reasons
                    ],
                }
                for page in loaded.pages
            ],
            "evidence": [
                {
                    "id": record.id,
                    "type": record.type,
                    "source_url_display": safe_display_url(record.source_url),
                    "collected_at": record.collected_at.isoformat(),
                    "sha256": record.sha256,
                    "page_id": record.page_id,
                    "artifact_available": True,
                }
                for record in sorted(loaded.evidence_by_id.values(), key=lambda item: item.id)
            ],
            "entities": [
                {
                    "id": entity.id,
                    "type": entity.type,
                    "display_value": safe_display_entity(entity.type, entity.normalized_value),
                    "source_evidence_id": entity.source_evidence_id,
                    "confidence": entity.confidence,
                    "source_page_id": loaded.evidence_by_id[entity.source_evidence_id].page_id,
                }
                for entity in loaded.entities
            ],
            "observations": [
                {
                    "id": observation.id,
                    "type": observation.observation_type,
                    "display_value": safe_display_entity(
                        observation.observation_type, observation.normalized_value
                    ),
                    "source_page_id": observation.source_page_id,
                    "source_artifact_id": observation.source_artifact_id,
                    "screenshot_evidence_id": observation.screenshot_evidence_id,
                    "crop_evidence_id": observation.crop_evidence_id,
                    "surrounding_text": _safe_text(observation.surrounding_text, 500),
                    "confidence": observation.confidence,
                    "evidence_strength": observation.evidence_strength,
                    "extraction_method": _safe_text(observation.extraction_method, 128),
                    "limitations": [_safe_text(item, 256) for item in observation.limitations],
                }
                for observation in loaded.observations
            ],
            "candidate_policy_version": (
                loaded.candidates.scoring_policy_version if loaded.candidates is not None else None
            ),
            "candidates": _display_candidates(
                loaded.candidates,
                case_id=loaded.case.case_id,
                evidence_ids=evidence_ids,
            ),
            "graph": (
                {
                    "node_count": len(loaded.graph.nodes),
                    "edge_count": len(loaded.graph.edges),
                    "schema_version": loaded.graph.metadata.get("schema_version"),
                    "nodes": [
                        {
                            "id": node.id,
                            "type": node.type,
                            "label": _safe_display_graph_label(node.type, node.label),
                        }
                        for node in loaded.graph.nodes
                    ],
                    "edges": [
                        _display_graph_edge(
                            edge,
                            graph_nodes,
                            evidence_ids,
                            case_id=loaded.case.case_id,
                        )
                        for edge in loaded.graph.edges
                    ],
                }
                if loaded.graph is not None
                else None
            ),
            "diagnostic": _display_diagnostic(
                loaded.diagnostics,
                evidence_ids,
                case_id=loaded.case.case_id,
            ),
            "diagnostic_integrity_warning": loaded.diagnostic_warning,
            "comparisons": _display_comparisons(comparisons or []),
            "comparison_integrity_warning": comparison_integrity_warning,
        }
    )
    return summary


def safe_display_url(raw_url: str | None) -> str | None:
    """Redact credentials/sensitive query values and return only a bounded inert display string."""

    if raw_url is None:
        return None
    try:
        parsed = urlsplit(raw_url)
        port = parsed.port
    except ValueError:
        return "[invalid URL]"
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        return "[invalid URL]"
    hostname = parsed.hostname.rstrip(".").casefold()
    host_display = f"[{hostname}]" if ":" in hostname else hostname
    default_port = 443 if parsed.scheme == "https" else 80
    netloc = host_display if port in (None, default_port) else f"{host_display}:{port}"
    safe_path = quote(parsed.path or "/", safe="/%:@-._~")
    try:
        query_pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=False)
    except ValueError:
        return "[redacted URL]"
    safe_query = "&".join(
        f"{quote(_safe_text(key, 64), safe='-._~')}={_display_query_value(key, value)}"
        for key, value in query_pairs[:30]
    )
    return _safe_text(
        urlunsplit((parsed.scheme, netloc, safe_path, safe_query, "")), max_length=512
    )


def safe_display_entity(entity_type: str, value: str) -> str:
    """Redact high-risk evidence values for UI display while preserving original disk evidence."""

    if entity_type in {
        "external_link",
        "external_asset_url",
        "public_outgoing_link",
        "public_redirect_target",
        "public_download_destination",
        "public_whatsapp_link",
    }:
        return safe_display_url(value) or "[invalid URL]"
    if entity_type in {"whatsapp_or_phone", "public_phone_number"}:
        compact = re.sub(r"\s+", "", value)
        if len(compact) > 4:
            return f"{compact[:2]}••••{compact[-4:]}"
    if entity_type in {"referral", "public_referral_code", "public_tracking_identifier"}:
        key, separator, _ = value.partition("=")
        return f"{_safe_text(key, 64)}=[redacted]" if separator else "[redacted referral]"
    return _safe_text(value, max_length=256)


def _display_collection_limits(case: CaseRecord) -> dict[str, int | float] | None:
    if case.crawl_configuration is None:
        return None
    configuration = case.crawl_configuration
    return {
        "max_depth": configuration.max_depth,
        "max_pages_total": configuration.max_pages_total,
        "max_redirects_per_page": configuration.max_redirects_per_page,
        "page_timeout_seconds": configuration.page_timeout_seconds,
        "case_timeout_seconds": configuration.case_timeout_seconds,
    }


def _display_candidates(
    candidates: CandidateDocument | None, *, case_id: str, evidence_ids: set[str]
) -> list[dict[str, Any]]:
    if candidates is None:
        return []
    return [
        {
            "candidate_id": candidate.candidate_id,
            "hostname": _safe_text(candidate.hostname, 255),
            "registrable_domain": _safe_text(candidate.registrable_domain, 255),
            "priority_score": candidate.discovery_priority_score,
            "status": candidate.status,
            "relationship": candidate.relationship,
            "reasons": [
                {
                    "reason_type": reason.reason_type,
                    "weight": reason.weight,
                    "evidence_refs": [
                        _display_evidence_reference(
                            reference.case_id,
                            reference.evidence_id,
                            observation_id=reference.observation_id,
                            available=(
                                reference.case_id == case_id
                                and reference.evidence_id in evidence_ids
                            ),
                        )
                        for reference in reason.supporting_evidence_refs
                    ],
                    "observation_ids": [
                        _safe_text(observation_id, 128)
                        for observation_id in reason.source_observation_ids
                    ],
                }
                for reason in candidate.reasons
            ],
        }
        for candidate in candidates.candidates
    ]


def _display_graph_edge(
    edge: Any, graph_nodes: dict[str, Any], evidence_ids: set[str], *, case_id: str
) -> dict[str, Any]:
    source = graph_nodes[edge.source]
    target = graph_nodes[edge.target]
    evidence_available = edge.evidence_id is not None and edge.evidence_id in evidence_ids
    return {
        "id": edge.id,
        "source": {
            "id": source.id,
            "type": source.type,
            "label": _safe_display_graph_label(source.type, source.label),
        },
        "type": edge.type,
        "target": {
            "id": target.id,
            "type": target.type,
            "label": _safe_display_graph_label(target.type, target.label),
        },
        "evidence": (
            _display_evidence_reference(
                case_id,
                edge.evidence_id,
                available=evidence_available,
            )
            if edge.evidence_id is not None
            else None
        ),
        "relationship_status": "observed_evidence"
        if edge.evidence_id is not None
        else "structural_record",
        "source_url_display": safe_display_url(edge.source_url),
        "extraction_method": _safe_text(edge.extraction_method, 128)
        if edge.extraction_method is not None
        else None,
        "confidence": edge.confidence,
    }


def _display_evidence_reference(
    case_id: str,
    evidence_id: str,
    *,
    available: bool,
    observation_id: str | None = None,
) -> dict[str, Any]:
    return {
        "case_id": _safe_text(case_id, 80),
        "evidence_id": _safe_text(evidence_id, 128),
        "observation_id": _safe_text(observation_id, 128) if observation_id is not None else None,
        "available": available,
    }


def _safe_display_graph_label(node_type: str, label: str) -> str:
    """Apply the same redaction boundary to graph labels that can contain captured values."""

    if node_type in {"page", "external_asset_url"}:
        return safe_display_url(label) or _safe_text(label, 256)
    if node_type in {"whatsapp_or_phone", "referral"}:
        return safe_display_entity(node_type, label)
    return _safe_text(label, 256)


def _display_diagnostic(
    diagnostic: RenderDiagnosticsDocument | None, evidence_ids: set[str], *, case_id: str
) -> dict[str, Any] | None:
    if diagnostic is None:
        return None
    return {
        "status": diagnostic.status,
        "collection_mode": diagnostic.collection_mode,
        "source_page_id": _safe_text(diagnostic.source_page_id, 80),
        "checkpoint_count": len(diagnostic.checkpoints),
        "diagnostic_wait_budget_ms": diagnostic.diagnostic_wait_budget_ms,
        "evidence_refs": [
            _display_evidence_reference(
                case_id,
                reference.evidence_id,
                available=reference.evidence_id in evidence_ids,
            )
            for reference in diagnostic.source_evidence_refs
        ],
    }


def _display_comparisons(comparisons: list[ComparisonDocument]) -> list[dict[str, Any]]:
    return [
        {
            "left_case_id": _safe_text(document.left_case_id, 80),
            "right_case_id": _safe_text(document.right_case_id, 80),
            "review_status": document.review_status,
            "evidence_similarity_score": document.candidate_mirror_score,
            "comparator_version": document.comparator_version,
            "scoring_policy_version": document.scoring_policy_version,
            "left_case_manifest_sha256": document.left_case_manifest_sha256,
            "right_case_manifest_sha256": document.right_case_manifest_sha256,
            "warnings": [_safe_text(warning, 256) for warning in document.warnings],
            "components": [
                {
                    "name": component.name,
                    "score": component.score,
                    "weight": component.weight,
                    "available": component.available,
                    "status": component.status,
                    "evidence_refs": [
                        _display_evidence_reference(
                            reference.case_id,
                            reference.evidence_id,
                            available=True,
                        )
                        for reference in component.evidence_refs
                    ],
                    "entity_refs": [
                        {
                            "case_id": _safe_text(reference.case_id, 80),
                            "entity_id": _safe_text(reference.entity_id, 128),
                            "evidence_id": _safe_text(reference.evidence_id, 128),
                            "type": _safe_text(reference.type, 80),
                        }
                        for reference in component.entity_refs
                    ],
                }
                for component in document.components
            ],
        }
        for document in comparisons
    ]


def _display_query_value(key: str, value: str) -> str:
    if _SENSITIVE_QUERY_KEY_RE.search(key) or len(value) > 64:
        return "[redacted]"
    return quote(_safe_text(value, 96), safe="-._~")


def _safe_text(value: str, max_length: int) -> str:
    visible = "".join(character for character in value if character >= " " and character != "\x7f")
    return visible[:max_length] + ("…" if len(visible) > max_length else "")


def _index_unique[T: BaseModel](records: list[T], record_name: str) -> dict[str, T]:
    indexed: dict[str, T] = {}
    for record in records:
        identifier = getattr(record, "id", None)
        if not isinstance(identifier, str) or not identifier or identifier in indexed:
            raise CaseIntegrityError(f"Case contains duplicate or invalid {record_name} IDs")
        indexed[identifier] = record
    return indexed


def _validate_page_and_entity_references(
    pages: list[CrawlPageRecord],
    evidence_by_id: dict[str, EvidenceRecord],
    entities: list[ExtractedEntity],
) -> None:
    for page in pages:
        _require_evidence_type(
            evidence_by_id,
            page.html_evidence_id,
            "html_page",
            page.id,
            required=page.content_usable,
        )
        _require_evidence_type(
            evidence_by_id, page.screenshot_evidence_id, "screenshot", page.id, required=False
        )
        _require_evidence_type(
            evidence_by_id,
            page.initial_screenshot_evidence_id,
            "initial_screenshot",
            page.id,
            required=False,
        )
        _require_evidence_type(
            evidence_by_id,
            page.full_page_screenshot_evidence_id,
            "full_page_screenshot",
            page.id,
            required=False,
        )
        _require_evidence_type(
            evidence_by_id,
            page.visible_text_evidence_id,
            "visible_text",
            page.id,
            required=False,
        )
        _require_evidence_type(
            evidence_by_id,
            page.response_metadata_evidence_id,
            "response_metadata",
            page.id,
            required=False,
        )
        _require_evidence_type(
            evidence_by_id,
            page.readiness_evidence_id,
            "capture_readiness",
            page.id,
            required=False,
        )
        _require_evidence_type(
            evidence_by_id, page.redirect_evidence_id, "network_event", page.id, required=False
        )
    for entity in entities:
        evidence = evidence_by_id.get(entity.source_evidence_id)
        if evidence is None or evidence.type != "html_page":
            raise CaseIntegrityError("Entity references missing or non-HTML evidence")


def _validate_semantic_observation_references(
    observations: list[SemanticObservation], evidence_by_id: dict[str, EvidenceRecord]
) -> None:
    """Fail closed when the semantic inspector could point at absent artifacts."""

    _index_unique(observations, "semantic observation")
    for observation in observations:
        source = evidence_by_id.get(observation.source_artifact_id)
        screenshot = evidence_by_id.get(observation.screenshot_evidence_id)
        crop = (
            evidence_by_id.get(observation.crop_evidence_id)
            if observation.crop_evidence_id is not None
            else None
        )
        if source is None:
            raise CaseIntegrityError("Semantic observation source artifact is missing")
        if screenshot is None or screenshot.type != "screenshot":
            raise CaseIntegrityError("Semantic observation screenshot evidence is invalid")
        if observation.crop_evidence_id is not None and (
            crop is None or crop.type != "evidence_crop"
        ):
            raise CaseIntegrityError("Semantic observation crop evidence is invalid")


def _require_evidence_type(
    evidence_by_id: dict[str, EvidenceRecord],
    evidence_id: str | None,
    expected_type: Literal[
        "html_page",
        "screenshot",
        "initial_screenshot",
        "full_page_screenshot",
        "visible_text",
        "response_metadata",
        "capture_readiness",
        "network_event",
    ],
    page_id: str,
    *,
    required: bool | None,
) -> None:
    if evidence_id is None:
        if required:
            raise CaseIntegrityError(f"Usable page is missing required evidence: {page_id}")
        return
    evidence = evidence_by_id.get(evidence_id)
    if evidence is None or evidence.type != expected_type:
        raise CaseIntegrityError(f"Page references missing or invalid {expected_type} evidence")


def _verify_all_evidence_artifacts(directory: Path, evidence: list[EvidenceRecord]) -> None:
    for record in evidence:
        _read_verified_artifact(directory, record)


def _read_verified_artifact(directory: Path, record: EvidenceRecord) -> bytes:
    artifact = _resolve_relative_regular_file(directory, record.path)
    byte_limit = _artifact_byte_limit(record)
    try:
        if artifact.stat().st_size > byte_limit:
            raise CaseIntegrityError("Evidence artifact exceeds review size limit")
        content = artifact.read_bytes()
    except OSError as error:
        raise CaseIntegrityError("Evidence artifact cannot be read") from error
    if len(content) > byte_limit:
        raise CaseIntegrityError("Evidence artifact exceeds review size limit")
    if hashlib.sha256(content).hexdigest() != record.sha256:
        raise CaseIntegrityError("Evidence artifact integrity verification failed")
    if record.type in {
        "screenshot",
        "initial_screenshot",
        "full_page_screenshot",
        "evidence_crop",
    }:
        _validate_screenshot(content, record)
    elif record.type in {"html_page", "visible_text"}:
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise CaseIntegrityError("Text evidence is not UTF-8") from error
    elif record.type in {"network_event", "response_metadata", "capture_readiness"}:
        try:
            json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CaseIntegrityError("JSON evidence is not valid") from error
    return content


def _artifact_byte_limit(record: EvidenceRecord) -> int:
    if record.type == "html_page":
        return _MAX_HTML_BYTES
    if record.type in {
        "screenshot",
        "initial_screenshot",
        "full_page_screenshot",
        "evidence_crop",
    }:
        return _MAX_SCREENSHOT_BYTES
    if record.type == "visible_text":
        return _MAX_TEXT_BYTES
    if record.type in {"network_event", "response_metadata", "capture_readiness"}:
        return _MAX_NETWORK_BYTES
    raise CaseIntegrityError("Evidence artifact type is not supported by the review console")


def _validate_screenshot(content: bytes, record: EvidenceRecord) -> None:
    """Verify a bounded PNG before presenting it as an image to the local browser UI."""

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                if image.format != "PNG":
                    raise CaseIntegrityError("Screenshot evidence is not PNG")
                width, height = image.size
                if width <= 0 or height <= 0 or width * height > _MAX_SCREENSHOT_PIXELS:
                    raise CaseIntegrityError("Screenshot evidence dimensions exceed review limits")
                image.load()
    except CaseIntegrityError:
        raise
    except (OSError, UnidentifiedImageError, ValueError, Warning) as error:
        raise CaseIntegrityError("Screenshot evidence cannot be safely decoded") from error
    if record.image_dimensions is not None and record.image_dimensions != {
        "width": width,
        "height": height,
    }:
        raise CaseIntegrityError("Screenshot evidence dimensions do not match its manifest")


def _artifact_response_policy(record: EvidenceRecord) -> tuple[str, str]:
    if record.type in {
        "screenshot",
        "initial_screenshot",
        "full_page_screenshot",
        "evidence_crop",
    }:
        return "image/png", 'inline; filename="evidence-screenshot.png"'
    if record.type == "html_page":
        return "text/plain; charset=utf-8", 'attachment; filename="evidence-page.html"'
    if record.type == "visible_text":
        return "text/plain; charset=utf-8", 'attachment; filename="evidence-visible.txt"'
    if record.type in {"network_event", "response_metadata", "capture_readiness"}:
        return "application/json; charset=utf-8", 'attachment; filename="evidence-network.json"'
    raise CaseIntegrityError("Evidence artifact type is not supported by the review console")


def _load_diagnostics(
    directory: Path,
    *,
    case_id: str,
    manifest_sha256: str,
    pages: list[CrawlPageRecord],
    evidence_by_id: dict[str, EvidenceRecord],
) -> tuple[RenderDiagnosticsDocument | None, str | None]:
    """Load an optional noncanonical diagnostic without weakening canonical case verification."""

    filename = "diagnostics/render-diagnostics.json"
    try:
        if not _file_exists(directory, filename):
            return None, None
        document = RenderDiagnosticsDocument.model_validate(_read_json(directory, filename))
    except (CaseIntegrityError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return None, _DIAGNOSTIC_WARNING
    if (
        document.source_case_id != case_id
        or document.source_case_manifest_sha256 != manifest_sha256
    ):
        return None, _DIAGNOSTIC_WARNING
    if document.source_page_id not in {page.id for page in pages}:
        return None, _DIAGNOSTIC_WARNING
    if document.checkpoint_schedule_ms != [0, 500, 1500, 3000] or not document.source_evidence_refs:
        return None, _DIAGNOSTIC_WARNING
    for reference in document.source_evidence_refs:
        evidence = evidence_by_id.get(reference.evidence_id)
        if (
            evidence is None
            or evidence.type != reference.type
            or evidence.sha256 != reference.sha256
        ):
            return None, _DIAGNOSTIC_WARNING
    return document, None


def _load_graph(directory: Path, evidence_by_id: dict[str, EvidenceRecord]) -> GraphDocument | None:
    if not _file_exists(directory, "graph.json"):
        return None
    try:
        graph = GraphDocument.model_validate(_read_json(directory, "graph.json"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise CaseIntegrityError("Graph JSON cannot be validated") from error
    _index_unique(graph.nodes, "graph node")
    _index_unique(graph.edges, "graph edge")
    node_ids = {node.id for node in graph.nodes}
    for edge in graph.edges:
        if edge.source not in node_ids or edge.target not in node_ids:
            raise CaseIntegrityError(
                "Graph edge references a graph node absent from the case manifest"
            )
        if edge.evidence_id is not None and edge.evidence_id not in evidence_by_id:
            raise CaseIntegrityError("Graph edge references evidence absent from the case manifest")
    return graph


def _load_candidates(
    directory: Path, case: CaseRecord, evidence_by_id: dict[str, EvidenceRecord]
) -> tuple[CandidateDocument | None, list[CandidateObservation]]:
    candidates_exists = _file_exists(directory, "candidates.json")
    observations_exists = _file_exists(directory, "candidate_observations.json")
    if candidates_exists != observations_exists:
        raise CaseIntegrityError(
            "Candidate document and observation artifacts must be present together"
        )
    if not candidates_exists:
        return None, []
    try:
        candidates = CandidateDocument.model_validate(_read_json(directory, "candidates.json"))
        observations = _models_from_json(
            directory, "candidate_observations.json", CandidateObservation
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise CaseIntegrityError("Candidate JSON cannot be validated") from error
    if candidates.source_case_id != case.case_id:
        raise CaseIntegrityError("Candidate document source case does not match the case directory")
    observation_by_id = _index_unique(observations, "candidate observation")
    for candidate in candidates.candidates:
        for reason in candidate.reasons:
            for observation_id in reason.source_observation_ids:
                if observation_id not in observation_by_id:
                    raise CaseIntegrityError("Candidate reason references a missing observation")
            for reference in reason.supporting_evidence_refs:
                if (
                    reference.case_id == case.case_id
                    and reference.evidence_id not in evidence_by_id
                ):
                    raise CaseIntegrityError("Candidate reason references missing local evidence")
    for observation in observations:
        if (
            observation.source_case_id == case.case_id
            and observation.source_evidence_id is not None
            and observation.discovery_method != "public_source"
            and observation.source_evidence_id not in evidence_by_id
        ):
            raise CaseIntegrityError("Candidate observation references missing local evidence")
    return candidates, observations


def _file_exists(directory: Path, filename: str) -> bool:
    relative = Path(filename)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or _path_has_reparse_point(directory, relative)
    ):
        raise CaseIntegrityError("Case JSON artifact must not be a reparse point")
    path = directory / relative
    return path.is_file()


def _read_comparison_document(path: Path) -> ComparisonDocument:
    """Parse one bounded immediate comparison file; callers validate its local references."""

    try:
        if path.stat().st_size > _MAX_COMPARISON_BYTES:
            raise CaseIntegrityError("Comparison document exceeds review size limit")
        content = path.read_bytes()
    except OSError as error:
        raise CaseIntegrityError("Comparison document cannot be read") from error
    if len(content) > _MAX_COMPARISON_BYTES:
        raise CaseIntegrityError("Comparison document exceeds review size limit")
    try:
        return ComparisonDocument.model_validate(json.loads(content))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise CaseIntegrityError("Comparison document cannot be validated") from error


def _read_json(directory: Path, filename: str) -> object:
    path = _resolve_relative_regular_file(directory, filename)
    try:
        if path.stat().st_size > _MAX_CASE_JSON_BYTES:
            raise CaseIntegrityError("Case JSON artifact exceeds review size limit")
        content = path.read_bytes()
    except OSError as error:
        raise CaseIntegrityError("Case JSON artifact cannot be read") from error
    if len(content) > _MAX_CASE_JSON_BYTES:
        raise CaseIntegrityError("Case JSON artifact exceeds review size limit")
    return json.loads(content)


def _models_from_json[T: BaseModel](directory: Path, filename: str, model_type: type[T]) -> list[T]:
    payload = _read_json(directory, filename)
    if not isinstance(payload, list):
        raise ValueError(f"Expected JSON list in {filename}")
    return [model_type.model_validate(item) for item in payload]


def _resolve_relative_regular_file(directory: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise CaseIntegrityError("Case artifact path is not a safe relative path")
    if _path_has_reparse_point(directory, relative):
        raise CaseIntegrityError("Case artifact reparse point is not allowed")
    try:
        resolved = (directory / relative).resolve()
    except OSError as error:
        raise CaseIntegrityError("Case artifact path cannot be resolved") from error
    if resolved == directory or directory not in resolved.parents or not resolved.is_file():
        raise CaseIntegrityError("Case artifact escapes the configured case directory")
    return resolved


def _is_reparse_point(path: Path) -> bool:
    try:
        is_junction = getattr(os.path, "isjunction", lambda _path: False)
        return path.is_symlink() or bool(is_junction(path))
    except OSError:
        return True


def _path_has_reparse_point(root: Path, relative_path: Path) -> bool:
    current = root
    for component in relative_path.parts:
        current = current / component
        if _is_reparse_point(current):
            return True
    return False


def _case_manifest(
    case: CaseRecord,
    pages: list[CrawlPageRecord],
    evidence: list[EvidenceRecord],
    entities: list[ExtractedEntity],
) -> str:
    payload = {
        "case": case.model_dump(mode="json"),
        "pages": [page.model_dump(mode="json") for page in sorted(pages, key=lambda page: page.id)],
        "evidence": [
            record.model_dump(mode="json")
            for record in sorted(evidence, key=lambda record: record.id)
        ],
        "entities": [
            entity.model_dump(mode="json")
            for entity in sorted(entities, key=lambda entity: entity.id)
        ],
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
