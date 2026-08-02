"""Deterministic V0.3 comparison of two existing local evidence cases."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import warnings
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Literal

from bs4 import BeautifulSoup
from PIL import Image
from pydantic import BaseModel

from hawkeye.candidates.normalization import (
    hostname_from_observed_url,
    is_common_asset_provider,
    is_generic_referral_signal,
)
from hawkeye.models import (
    CaseRecord,
    ComparisonComponent,
    ComparisonDocument,
    ComparisonEntityReference,
    ComparisonEvidenceReference,
    CrawlPageRecord,
    EvidenceRecord,
    ExtractedEntity,
)

_TEXT_TOKEN_RE = re.compile(r"[\w]{2,}", re.UNICODE)
_ENTITY_TYPES = frozenset({"telegram", "whatsapp_or_phone", "referral"})
_WEIGHTS: dict[str, float] = {
    "shared_entity_similarity": 0.30,
    "visible_text_similarity": 0.20,
    "dom_structure_similarity": 0.20,
    "screenshot_perceptual_similarity": 0.20,
    "shared_asset_similarity": 0.10,
}
_MIN_TEXT_TOKENS = 6
_MIN_DOM_FEATURES = 3
_MIN_SCREENSHOT_VARIANCE = 16.0
_MAX_HTML_BYTES = 2_000_000
_MAX_SCREENSHOT_BYTES = 10_000_000
_MAX_SCREENSHOT_PIXELS = 25_000_000
_IGNORED_DOM_TAGS = frozenset({"script", "style", "noscript", "template"})
ComponentStatus = Literal["scored", "not_applicable", "low_information"]


class ComparisonInputError(ValueError):
    """Raised when a local case cannot be safely and completely verified for comparison."""


@dataclass(frozen=True)
class _VerifiedArtifact:
    """One integrity-checked local evidence artifact."""

    evidence: EvidenceRecord
    content: bytes


@dataclass(frozen=True)
class _LoadedCase:
    """The bounded, verified subset of a persisted case usable by V0.3."""

    directory: Path
    case: CaseRecord
    pages: list[CrawlPageRecord]
    evidence_by_id: dict[str, EvidenceRecord]
    entities: list[ExtractedEntity]
    html_artifacts: dict[str, _VerifiedArtifact]
    screenshot_artifacts: dict[str, _VerifiedArtifact]
    manifest_sha256: str


@dataclass(frozen=True)
class _ScreenshotFingerprint:
    """A deterministic 256-bit average hash plus a low-information quality measure."""

    value: int
    variance: float


def compare_cases(
    left_case_directory: Path | str, right_case_directory: Path | str
) -> ComparisonDocument:
    """Compare two existing local cases without DNS, HTTP, browser, or candidate navigation."""

    left = _load_case(Path(left_case_directory))
    right = _load_case(Path(right_case_directory))
    if left.directory == right.directory:
        raise ComparisonInputError("Comparison requires two distinct completed cases")
    if left.manifest_sha256 == right.manifest_sha256:
        raise ComparisonInputError("Comparison rejects identical case manifests")
    if left.case.case_id == right.case.case_id:
        raise ComparisonInputError("Comparison requires two distinct completed cases")
    comparison_warnings: list[str] = []
    if not left.html_artifacts:
        comparison_warnings.append(
            f"left case {left.case.case_id} has no usable verified HTML artifacts"
        )
    if not right.html_artifacts:
        comparison_warnings.append(
            f"right case {right.case.case_id} has no usable verified HTML artifacts"
        )

    components = [
        _shared_entity_component(left, right),
        _visible_text_component(left, right),
        _dom_structure_component(left, right),
        _screenshot_component(left, right),
        _shared_asset_component(left, right),
    ]
    for component in components:
        if not component.available:
            comparison_warnings.append(
                f"{component.name} {component.status} from the verified source artifacts"
            )
    mirror_score = round(
        100 * sum(component.score * component.weight for component in components),
        2,
    )
    return ComparisonDocument(
        left_case_id=left.case.case_id,
        right_case_id=right.case.case_id,
        left_final_url=left.case.final_url,
        right_final_url=right.case.final_url,
        left_case_manifest_sha256=left.manifest_sha256,
        right_case_manifest_sha256=right.manifest_sha256,
        weights=_WEIGHTS,
        candidate_mirror_score=mirror_score,
        components=components,
        warnings=comparison_warnings,
        generated_at=datetime.now(UTC),
    )


def write_comparison(document: ComparisonDocument, output_path: Path | str) -> Path:
    """Persist one comparison JSON file without overwriting an existing result."""

    destination = Path(output_path).expanduser().resolve()
    if destination.suffix.casefold() != ".json":
        raise ValueError("Comparison output path must end in .json")
    if destination.exists():
        raise FileExistsError(f"Comparison output already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(
        document.model_dump(mode="json"), indent=2, sort_keys=True, ensure_ascii=False
    )
    destination.write_text(f"{serialized}\n", encoding="utf-8")
    return destination


def _load_case(directory: Path) -> _LoadedCase:
    requested_root = directory.expanduser()
    if _is_reparse_point(requested_root):
        raise ComparisonInputError(f"Case directory reparse point is not allowed: {directory}")
    try:
        root = requested_root.resolve()
    except OSError as error:
        raise ComparisonInputError(f"Unable to resolve case directory: {directory}") from error
    if not root.is_dir():
        raise ComparisonInputError(f"Case directory does not exist: {root}")
    try:
        case = CaseRecord.model_validate(_read_json(root / "case.json"))
        pages = _models_from_json(root / "pages.json", CrawlPageRecord)
        evidence = _models_from_json(root / "evidence.json", EvidenceRecord)
        entities = _models_from_json(root / "entities.json", ExtractedEntity)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ComparisonInputError(f"Invalid case artifacts in {root}: {error}") from error
    if case.status != "completed":
        raise ComparisonInputError(f"Case is not completed: {case.case_id}")

    evidence_by_id = {record.id: record for record in evidence}
    html_artifacts: dict[str, _VerifiedArtifact] = {}
    screenshot_artifacts: dict[str, _VerifiedArtifact] = {}
    usable_html_ids: set[str] = set()
    seen_html_sha256: set[str] = set()
    for page in sorted(pages, key=lambda item: item.id):
        if page.state != "completed" or page.content_usable is not True:
            continue
        if page.duplicate_of_page_id is not None:
            continue
        if page.html_evidence_id is None:
            raise ComparisonInputError(
                f"Usable page has no HTML evidence: {case.case_id}/{page.id}"
            )
        html_record = evidence_by_id.get(page.html_evidence_id)
        if html_record is None or html_record.type != "html_page":
            raise ComparisonInputError(
                f"Usable page HTML evidence is missing or invalid: {case.case_id}/{page.id}"
            )
        html_artifact = _read_verified_artifact(root, html_record)
        _parse_html(html_artifact.content, case.case_id, page.id)
        if html_record.sha256 in seen_html_sha256:
            continue
        seen_html_sha256.add(html_record.sha256)
        html_artifacts[page.id] = html_artifact
        usable_html_ids.add(html_record.id)
        if page.screenshot_evidence_id is None:
            continue
        screenshot_record = evidence_by_id.get(page.screenshot_evidence_id)
        if screenshot_record is None or screenshot_record.type != "screenshot":
            raise ComparisonInputError(
                f"Usable page screenshot evidence is missing or invalid: {case.case_id}/{page.id}"
            )
        screenshot_artifact = _read_verified_artifact(root, screenshot_record)
        _validate_screenshot(screenshot_artifact.content, screenshot_record, case.case_id, page.id)
        screenshot_artifacts[page.id] = screenshot_artifact

    usable_entities = sorted(
        (entity for entity in entities if entity.source_evidence_id in usable_html_ids),
        key=lambda entity: (entity.type, entity.normalized_value, entity.id),
    )
    return _LoadedCase(
        directory=root,
        case=case,
        pages=pages,
        evidence_by_id=evidence_by_id,
        entities=usable_entities,
        html_artifacts=html_artifacts,
        screenshot_artifacts=screenshot_artifacts,
        manifest_sha256=_case_manifest(case, pages, evidence, entities),
    )


def _read_verified_artifact(root: Path, record: EvidenceRecord) -> _VerifiedArtifact:
    relative_path = Path(record.path)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ComparisonInputError(f"Evidence artifact path is not relative: {record.id}")
    untrusted_path = root / relative_path
    if _path_has_reparse_point(root, relative_path):
        raise ComparisonInputError(f"Evidence artifact reparse point is not allowed: {record.id}")
    try:
        artifact = untrusted_path.resolve()
    except OSError as error:
        raise ComparisonInputError(
            f"Unable to resolve evidence artifact {record.id} in {root}"
        ) from error
    if artifact == root or root not in artifact.parents:
        raise ComparisonInputError(f"Evidence artifact escapes case directory: {record.id}")
    try:
        if not artifact.is_file():
            raise ComparisonInputError(f"Evidence artifact is not a regular file: {record.id}")
        byte_limit = _artifact_byte_limit(record)
        if artifact.stat().st_size > byte_limit:
            raise ComparisonInputError(f"Evidence artifact exceeds comparison limit: {record.id}")
        content = artifact.read_bytes()
    except ComparisonInputError:
        raise
    except OSError as error:
        raise ComparisonInputError(f"Evidence artifact is missing: {record.id}") from error
    digest = hashlib.sha256(content).hexdigest()
    if digest != record.sha256:
        raise ComparisonInputError(f"Evidence artifact integrity mismatch: {record.id}")
    if len(content) > _artifact_byte_limit(record):
        raise ComparisonInputError(f"Evidence artifact exceeds comparison limit: {record.id}")
    return _VerifiedArtifact(evidence=record, content=content)


def _shared_entity_component(left: _LoadedCase, right: _LoadedCase) -> ComparisonComponent:
    left_index = _entity_index(left, _ENTITY_TYPES)
    right_index = _entity_index(right, _ENTITY_TYPES)
    scored_type_values: list[float] = []
    shared: list[tuple[str, str]] = []
    per_type: dict[str, dict[str, float | int]] = {}
    for entity_type in sorted(_ENTITY_TYPES):
        left_values = {value for type_name, value in left_index if type_name == entity_type}
        right_values = {value for type_name, value in right_index if type_name == entity_type}
        union = left_values | right_values
        intersection = left_values & right_values
        shared.extend((entity_type, value) for value in sorted(intersection))
        if union:
            score = _jaccard(left_values, right_values)
            scored_type_values.append(score)
            per_type[entity_type] = {
                "left_count": len(left_values),
                "right_count": len(right_values),
                "intersection_count": len(intersection),
                "union_count": len(union),
                "score": score,
            }
        else:
            per_type[entity_type] = {
                "left_count": 0,
                "right_count": 0,
                "intersection_count": 0,
                "union_count": 0,
            }
    shared.sort()
    references = _entity_references(left, left_index, sorted(left_index)) + _entity_references(
        right, right_index, sorted(right_index)
    )
    available = bool(scored_type_values)
    return ComparisonComponent(
        name="shared_entity_similarity",
        score=round(sum(scored_type_values) / len(scored_type_values), 6) if available else 0.0,
        weight=_WEIGHTS["shared_entity_similarity"],
        available=available,
        status="scored" if available else "not_applicable",
        evidence_refs=_evidence_refs_for_entity_references(left, right, references),
        entity_refs=references,
        details={
            "aggregation": "mean_of_entity_type_jaccard_scores_with_nonempty_union",
            "per_type": per_type,
            "shared_entity_count": len(shared),
            "shared_values": [f"{entity_type}:{value}" for entity_type, value in shared],
        },
    )


def _visible_text_component(left: _LoadedCase, right: _LoadedCase) -> ComparisonComponent:
    pair_details: list[dict[str, object]] = []
    pair_scores: list[float] = []
    scored_pairs = 0
    for left_page_id, left_artifact, right_page_id, right_artifact in _page_pairs(
        left, right, "html"
    ):
        left_tokens = (
            _text_tokens_from_artifact(left_artifact) if left_artifact is not None else Counter()
        )
        right_tokens = (
            _text_tokens_from_artifact(right_artifact) if right_artifact is not None else Counter()
        )
        pair_score = 0.0
        status: ComponentStatus
        if left_artifact is None or right_artifact is None:
            status = "not_applicable"
        elif min(sum(left_tokens.values()), sum(right_tokens.values())) < _MIN_TEXT_TOKENS:
            status = "low_information"
        else:
            pair_score = _cosine_similarity(left_tokens, right_tokens)
            status = "scored"
            scored_pairs += 1
        pair_scores.append(pair_score)
        pair_details.append(
            {
                "left_page_id": left_page_id,
                "right_page_id": right_page_id,
                "left_token_count": sum(left_tokens.values()),
                "right_token_count": sum(right_tokens.values()),
                "score": pair_score,
                "status": status,
            }
        )
    status = _aggregate_status(
        scored_pairs=scored_pairs,
        has_left=bool(left.html_artifacts),
        has_right=bool(right.html_artifacts),
    )
    return ComparisonComponent(
        name="visible_text_similarity",
        score=_average_or_zero(pair_scores),
        weight=_WEIGHTS["visible_text_similarity"],
        available=status == "scored",
        status=status,
        evidence_refs=_all_html_refs(left) + _all_html_refs(right),
        details={
            "aggregation": "ordered_one_to_one_page_pairs_with_unmatched_pages_scoring_zero",
            "minimum_tokens_per_page": _MIN_TEXT_TOKENS,
            "page_pairs": pair_details,
        },
    )


def _dom_structure_component(left: _LoadedCase, right: _LoadedCase) -> ComparisonComponent:
    pair_details: list[dict[str, object]] = []
    pair_scores: list[float] = []
    scored_pairs = 0
    for left_page_id, left_artifact, right_page_id, right_artifact in _page_pairs(
        left, right, "html"
    ):
        left_features = (
            _dom_features_from_artifact(left_artifact) if left_artifact is not None else []
        )
        right_features = (
            _dom_features_from_artifact(right_artifact) if right_artifact is not None else []
        )
        pair_score = 0.0
        status: ComponentStatus
        if left_artifact is None or right_artifact is None:
            status = "not_applicable"
        elif min(len(left_features), len(right_features)) < _MIN_DOM_FEATURES:
            status = "low_information"
        else:
            pair_score = _jaccard(set(left_features), set(right_features))
            status = "scored"
            scored_pairs += 1
        pair_scores.append(pair_score)
        pair_details.append(
            {
                "left_page_id": left_page_id,
                "right_page_id": right_page_id,
                "left_feature_count": len(left_features),
                "right_feature_count": len(right_features),
                "intersection_count": len(set(left_features) & set(right_features)),
                "union_count": len(set(left_features) | set(right_features)),
                "score": pair_score,
                "status": status,
            }
        )
    status = _aggregate_status(
        scored_pairs=scored_pairs,
        has_left=bool(left.html_artifacts),
        has_right=bool(right.html_artifacts),
    )
    return ComparisonComponent(
        name="dom_structure_similarity",
        score=_average_or_zero(pair_scores),
        weight=_WEIGHTS["dom_structure_similarity"],
        available=status == "scored",
        status=status,
        evidence_refs=_all_html_refs(left) + _all_html_refs(right),
        details={
            "aggregation": "ordered_one_to_one_page_pairs_with_unmatched_pages_scoring_zero",
            "minimum_features_per_page": _MIN_DOM_FEATURES,
            "feature_representation": "tag_name_with_sorted_attribute_names; values are ignored",
            "ignored_tags": sorted(_IGNORED_DOM_TAGS),
            "page_pairs": pair_details,
        },
    )


def _screenshot_component(left: _LoadedCase, right: _LoadedCase) -> ComparisonComponent:
    pair_details: list[dict[str, object]] = []
    pair_scores: list[float] = []
    refs: list[ComparisonEvidenceReference] = []
    scored_pairs = 0
    for left_page_id, left_artifact, right_page_id, right_artifact in _page_pairs(
        left, right, "screenshot"
    ):
        pair_score = 0.0
        status: ComponentStatus
        detail: dict[str, object] = {
            "left_page_id": left_page_id,
            "right_page_id": right_page_id,
        }
        if left_artifact is not None:
            refs.append(_evidence_ref(left.case.case_id, left_artifact.evidence))
        if right_artifact is not None:
            refs.append(_evidence_ref(right.case.case_id, right_artifact.evidence))
        if left_artifact is None or right_artifact is None:
            status = "not_applicable"
        elif not _compatible_screenshots(left_artifact.evidence, right_artifact.evidence):
            status = "not_applicable"
            detail["metadata_compatible"] = False
        else:
            left_hash = _perceptual_hash(left_artifact.content)
            right_hash = _perceptual_hash(right_artifact.content)
            detail.update(
                {
                    "metadata_compatible": True,
                    "left_hash": f"{left_hash.value:064x}",
                    "right_hash": f"{right_hash.value:064x}",
                    "left_pixel_variance": left_hash.variance,
                    "right_pixel_variance": right_hash.variance,
                }
            )
            if min(left_hash.variance, right_hash.variance) < _MIN_SCREENSHOT_VARIANCE:
                status = "low_information"
            else:
                distance = (left_hash.value ^ right_hash.value).bit_count()
                pair_score = 1.0 - distance / 256
                detail["hamming_distance"] = distance
                status = "scored"
                scored_pairs += 1
        detail["score"] = round(pair_score, 6)
        detail["status"] = status
        pair_scores.append(pair_score)
        pair_details.append(detail)
    status = _aggregate_status(
        scored_pairs=scored_pairs,
        has_left=bool(left.screenshot_artifacts),
        has_right=bool(right.screenshot_artifacts),
    )
    return ComparisonComponent(
        name="screenshot_perceptual_similarity",
        score=_average_or_zero(pair_scores),
        weight=_WEIGHTS["screenshot_perceptual_similarity"],
        available=status == "scored",
        status=status,
        evidence_refs=sorted(
            {(reference.case_id, reference.evidence_id): reference for reference in refs}.values(),
            key=lambda reference: (reference.case_id, reference.evidence_id),
        ),
        details={
            "aggregation": "ordered_one_to_one_page_pairs_with_unmatched_pages_scoring_zero",
            "minimum_pixel_variance": _MIN_SCREENSHOT_VARIANCE,
            "page_pairs": pair_details,
        },
    )


def _shared_asset_component(left: _LoadedCase, right: _LoadedCase) -> ComparisonComponent:
    left_index = _entity_index(left, {"external_asset_url"})
    right_index = _entity_index(right, {"external_asset_url"})
    left_keys = set(left_index)
    right_keys = set(right_index)
    shared = sorted(left_keys & right_keys)
    references = _entity_references(left, left_index, sorted(left_index)) + _entity_references(
        right, right_index, sorted(right_index)
    )
    available = bool(left_keys | right_keys)
    return ComparisonComponent(
        name="shared_asset_similarity",
        score=_jaccard(left_keys, right_keys) if available else 0.0,
        weight=_WEIGHTS["shared_asset_similarity"],
        available=available,
        status="scored" if available else "not_applicable",
        evidence_refs=_evidence_refs_for_entity_references(left, right, references),
        entity_refs=references,
        details={
            "left_asset_count": len(left_keys),
            "right_asset_count": len(right_keys),
            "shared_asset_count": len(shared),
            "shared_exact_asset_urls": [value for _, value in shared],
        },
    )


def _entity_index(
    case: _LoadedCase, allowed_types: set[str] | frozenset[str]
) -> dict[tuple[str, str], list[ExtractedEntity]]:
    indexed: dict[tuple[str, str], list[ExtractedEntity]] = defaultdict(list)
    for entity in case.entities:
        if entity.type in allowed_types and _is_comparable_entity(entity):
            indexed[(entity.type, entity.normalized_value)].append(entity)
    return indexed


def _entity_references(
    case: _LoadedCase,
    index: dict[tuple[str, str], list[ExtractedEntity]],
    keys: list[tuple[str, str]],
) -> list[ComparisonEntityReference]:
    references = [
        ComparisonEntityReference(
            case_id=case.case.case_id,
            entity_id=entity.id,
            evidence_id=entity.source_evidence_id,
            type=entity.type,
            normalized_value=entity.normalized_value,
        )
        for key in keys
        for entity in index[key]
    ]
    return sorted(
        references,
        key=lambda reference: (
            reference.case_id,
            reference.type,
            reference.normalized_value,
            reference.entity_id,
        ),
    )


def _evidence_refs_for_entity_references(
    left: _LoadedCase,
    right: _LoadedCase,
    references: list[ComparisonEntityReference],
) -> list[ComparisonEvidenceReference]:
    cases = {left.case.case_id: left, right.case.case_id: right}
    selected: dict[tuple[str, str], ComparisonEvidenceReference] = {}
    for reference in references:
        case = cases[reference.case_id]
        evidence = case.evidence_by_id[reference.evidence_id]
        selected[(reference.case_id, reference.evidence_id)] = _evidence_ref(
            reference.case_id, evidence
        )
    return sorted(
        selected.values(), key=lambda reference: (reference.case_id, reference.evidence_id)
    )


def _all_html_refs(case: _LoadedCase) -> list[ComparisonEvidenceReference]:
    return [
        _evidence_ref(case.case.case_id, artifact.evidence)
        for _, artifact in sorted(case.html_artifacts.items())
    ]


def _evidence_ref(case_id: str, evidence: EvidenceRecord) -> ComparisonEvidenceReference:
    return ComparisonEvidenceReference(
        case_id=case_id,
        evidence_id=evidence.id,
        path=evidence.path,
        sha256=evidence.sha256,
    )


def _artifact_byte_limit(record: EvidenceRecord) -> int:
    if record.type == "html_page":
        return _MAX_HTML_BYTES
    if record.type == "screenshot":
        return _MAX_SCREENSHOT_BYTES
    raise ComparisonInputError(f"Unsupported comparison artifact type: {record.id}")


def _is_reparse_point(path: Path) -> bool:
    """Reject symlinks and Windows junctions before trusted local artifact reads."""

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
    """Hash exactly the persisted V0.3 comparison inputs, never derived output files."""

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
    serialized = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _parse_html(content: bytes, case_id: str, page_id: str) -> BeautifulSoup:
    """Decode and parse the already integrity-verified bytes without a second file read."""

    try:
        decoded = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ComparisonInputError(f"HTML artifact is not UTF-8: {case_id}/{page_id}") from error
    return BeautifulSoup(decoded, "html.parser")


def _validate_screenshot(
    content: bytes, evidence: EvidenceRecord, case_id: str, page_id: str
) -> None:
    """Bound PNG decoding and require metadata to describe the exact stored pixels."""

    if evidence.viewport is None or evidence.image_dimensions is None:
        raise ComparisonInputError(f"Screenshot metadata is missing: {case_id}/{page_id}")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                if image.format != "PNG":
                    raise ComparisonInputError(
                        f"Screenshot artifact is not PNG: {case_id}/{page_id}"
                    )
                width, height = image.size
                if width <= 0 or height <= 0 or width * height > _MAX_SCREENSHOT_PIXELS:
                    raise ComparisonInputError(
                        f"Screenshot dimensions exceed comparison limit: {case_id}/{page_id}"
                    )
                image.load()
    except ComparisonInputError:
        raise
    except (OSError, ValueError, Warning) as error:
        raise ComparisonInputError(
            f"Screenshot artifact cannot be safely decoded: {case_id}/{page_id}"
        ) from error
    actual_dimensions = {"width": width, "height": height}
    if evidence.image_dimensions != actual_dimensions:
        raise ComparisonInputError(f"Screenshot image metadata mismatch: {case_id}/{page_id}")
    if not _valid_dimensions(evidence.viewport) or not _valid_dimensions(evidence.image_dimensions):
        raise ComparisonInputError(
            f"Screenshot metadata dimensions are invalid: {case_id}/{page_id}"
        )
    if evidence.viewport != evidence.image_dimensions:
        raise ComparisonInputError(f"Screenshot viewport metadata mismatch: {case_id}/{page_id}")


def _valid_dimensions(dimensions: dict[str, int]) -> bool:
    return set(dimensions) == {"width", "height"} and all(
        isinstance(value, int) and not isinstance(value, bool) and value > 0
        for value in dimensions.values()
    )


def _page_pairs(
    left: _LoadedCase,
    right: _LoadedCase,
    artifact_type: Literal["html", "screenshot"],
) -> list[
    tuple[
        str | None,
        _VerifiedArtifact | None,
        str | None,
        _VerifiedArtifact | None,
    ]
]:
    """Pair unique pages by stable page ID order; unmatched pages deliberately score zero."""

    left_artifacts = left.html_artifacts if artifact_type == "html" else left.screenshot_artifacts
    right_artifacts = (
        right.html_artifacts if artifact_type == "html" else right.screenshot_artifacts
    )
    left_items = sorted(left_artifacts.items())
    right_items = sorted(right_artifacts.items())
    pairs: list[
        tuple[
            str | None,
            _VerifiedArtifact | None,
            str | None,
            _VerifiedArtifact | None,
        ]
    ] = []
    for index in range(max(len(left_items), len(right_items))):
        left_page_id, left_artifact = left_items[index] if index < len(left_items) else (None, None)
        right_page_id, right_artifact = (
            right_items[index] if index < len(right_items) else (None, None)
        )
        pairs.append((left_page_id, left_artifact, right_page_id, right_artifact))
    return pairs


def _aggregate_status(*, scored_pairs: int, has_left: bool, has_right: bool) -> ComponentStatus:
    if not has_left or not has_right:
        return "not_applicable"
    if scored_pairs:
        return "scored"
    return "low_information"


def _average_or_zero(scores: list[float]) -> float:
    return round(sum(scores) / len(scores), 6) if scores else 0.0


def _text_tokens_from_artifact(artifact: _VerifiedArtifact) -> Counter[str]:
    soup = _parse_html(
        artifact.content, "comparison", artifact.evidence.page_id or artifact.evidence.id
    )
    for element in soup.find_all(_IGNORED_DOM_TAGS):
        element.decompose()
    return Counter(_TEXT_TOKEN_RE.findall(soup.get_text(" ", strip=True).casefold()))


def _dom_features_from_artifact(artifact: _VerifiedArtifact) -> list[tuple[str, str]]:
    soup = _parse_html(
        artifact.content, "comparison", artifact.evidence.page_id or artifact.evidence.id
    )
    sequence = [
        f"{element.name}[{','.join(sorted(element.attrs))}]"
        for element in soup.find_all(True)
        if element.name not in _IGNORED_DOM_TAGS
    ]
    if len(sequence) == 1:
        return [(sequence[0], "")]
    return list(zip(sequence, sequence[1:], strict=False))


def _compatible_screenshots(left: EvidenceRecord, right: EvidenceRecord) -> bool:
    return (
        left.viewport is not None
        and left.image_dimensions is not None
        and left.viewport == right.viewport
        and left.image_dimensions == right.image_dimensions
    )


def _perceptual_hash(content: bytes) -> _ScreenshotFingerprint:
    with Image.open(BytesIO(content)) as image:
        image.load()
        pixels = list(image.convert("L").resize((16, 16), Image.Resampling.LANCZOS).tobytes())
    average = sum(pixels) / len(pixels)
    variance = sum((value - average) ** 2 for value in pixels) / len(pixels)
    value = sum(1 << index for index, pixel in enumerate(pixels) if pixel >= average)
    return _ScreenshotFingerprint(value=value, variance=round(variance, 6))


def _is_comparable_entity(entity: ExtractedEntity) -> bool:
    """Reuse V0.2's suppression policy for noisy generic comparison signals."""

    if entity.type == "referral":
        return not is_generic_referral_signal(entity.normalized_value)
    if entity.type == "external_asset_url":
        return not is_common_asset_provider(hostname_from_observed_url(entity.normalized_value))
    return True


def _jaccard[T](left: set[T], right: set[T]) -> float:
    union = left | right
    return round(len(left & right) / len(union), 6) if union else 0.0


def _cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
    dot_product = sum(count * right[token] for token, count in left.items())
    left_norm = math.sqrt(sum(count * count for count in left.values()))
    right_norm = math.sqrt(sum(count * count for count in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return round(dot_product / (left_norm * right_norm), 6)


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _models_from_json[T: BaseModel](path: Path, model_type: type[T]) -> list[T]:
    payload = _read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"Expected JSON list in {path}")
    return [model_type.model_validate(item) for item in payload]
