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

from hawkeye.models import (
    CandidateDocument,
    CandidateObservation,
    CaseRecord,
    CrawlPageRecord,
    EvidenceRecord,
    ExtractedEntity,
    GraphDocument,
)

_CASE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
_SENSITIVE_QUERY_KEY_RE = re.compile(
    r"(?:api[-_]?key|auth(?:orization)?|code|credential|pass(?:word)?|secret|session|sid|token)",
    re.IGNORECASE,
)
_MAX_CASE_JSON_BYTES = 2_000_000
_MAX_HTML_BYTES = 2_000_000
_MAX_SCREENSHOT_BYTES = 10_000_000
_MAX_NETWORK_BYTES = 1_000_000
_MAX_SCREENSHOT_PIXELS = 25_000_000


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
    candidates: CandidateDocument | None
    candidate_observations: list[CandidateObservation]
    graph: GraphDocument | None
    manifest_sha256: str


@dataclass(frozen=True)
class ArtifactPayload:
    """A verified artifact body plus the one safe response representation for its known type."""

    content: bytes
    media_type: str
    disposition: str


class CaseLoader:
    """Resolve case and artifact IDs through verified manifests only; never accept paths."""

    def __init__(self, cases_root: Path | str) -> None:
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
        _verify_all_evidence_artifacts(directory, evidence)
        graph = _load_graph(directory, evidence_by_id)
        candidates, candidate_observations = _load_candidates(directory, case, evidence_by_id)
        return LoadedCase(
            directory=directory,
            case=case,
            pages=sorted(pages, key=lambda page: page.id),
            evidence_by_id=evidence_by_id,
            entities=sorted(entities, key=lambda entity: entity.id),
            candidates=candidates,
            candidate_observations=sorted(candidate_observations, key=lambda item: item.id),
            graph=graph,
            manifest_sha256=_case_manifest(case, pages, evidence, entities),
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
        "page_count": loaded.case.page_count,
        "candidate_count": loaded.case.candidate_count,
        "case_manifest_sha256": loaded.manifest_sha256,
    }


def case_details(loaded: LoadedCase) -> dict[str, Any]:
    """Project a verified package into a UI-safe, relationship-neutral review model."""

    summary = case_summary(loaded)
    summary.update(
        {
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
                    "html_evidence_id": page.html_evidence_id,
                    "screenshot_evidence_id": page.screenshot_evidence_id,
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
                }
                for entity in loaded.entities
            ],
            "candidates": _display_candidates(loaded.candidates),
            "graph": (
                {
                    "node_count": len(loaded.graph.nodes),
                    "edge_count": len(loaded.graph.edges),
                    "schema_version": loaded.graph.metadata.get("schema_version"),
                }
                if loaded.graph is not None
                else None
            ),
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

    if entity_type in {"external_link", "external_asset_url"}:
        return safe_display_url(value) or "[invalid URL]"
    if entity_type == "whatsapp_or_phone":
        compact = re.sub(r"\s+", "", value)
        if len(compact) > 4:
            return f"{compact[:2]}••••{compact[-4:]}"
    if entity_type == "referral":
        key, separator, _ = value.partition("=")
        return f"{_safe_text(key, 64)}=[redacted]" if separator else "[redacted referral]"
    return _safe_text(value, max_length=256)


def _display_candidates(candidates: CandidateDocument | None) -> list[dict[str, Any]]:
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
                    "evidence_ids": reason.supporting_evidence_ids,
                    "observation_ids": reason.source_observation_ids,
                }
                for reason in candidate.reasons
            ],
        }
        for candidate in candidates.candidates
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
            evidence_by_id, page.redirect_evidence_id, "network_event", page.id, required=False
        )
    for entity in entities:
        evidence = evidence_by_id.get(entity.source_evidence_id)
        if evidence is None or evidence.type != "html_page":
            raise CaseIntegrityError("Entity references missing or non-HTML evidence")


def _require_evidence_type(
    evidence_by_id: dict[str, EvidenceRecord],
    evidence_id: str | None,
    expected_type: Literal["html_page", "screenshot", "network_event"],
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
    if record.type == "screenshot":
        _validate_screenshot(content, record)
    elif record.type == "html_page":
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise CaseIntegrityError("HTML evidence is not UTF-8") from error
    elif record.type == "network_event":
        try:
            json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CaseIntegrityError("Network evidence is not valid JSON") from error
    return content


def _artifact_byte_limit(record: EvidenceRecord) -> int:
    if record.type == "html_page":
        return _MAX_HTML_BYTES
    if record.type == "screenshot":
        return _MAX_SCREENSHOT_BYTES
    if record.type == "network_event":
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
    if record.type == "screenshot":
        return "image/png", 'inline; filename="evidence-screenshot.png"'
    if record.type == "html_page":
        return "text/plain; charset=utf-8", 'attachment; filename="evidence-page.html"'
    if record.type == "network_event":
        return "application/json; charset=utf-8", 'attachment; filename="evidence-network.json"'
    raise CaseIntegrityError("Evidence artifact type is not supported by the review console")


def _load_graph(directory: Path, evidence_by_id: dict[str, EvidenceRecord]) -> GraphDocument | None:
    if not _file_exists(directory, "graph.json"):
        return None
    try:
        graph = GraphDocument.model_validate(_read_json(directory, "graph.json"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise CaseIntegrityError("Graph JSON cannot be validated") from error
    _index_unique(graph.nodes, "graph node")
    _index_unique(graph.edges, "graph edge")
    for edge in graph.edges:
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
    path = directory / filename
    if _is_reparse_point(path):
        raise CaseIntegrityError("Case JSON artifact must not be a reparse point")
    return path.is_file()


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
