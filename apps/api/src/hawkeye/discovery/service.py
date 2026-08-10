"""V0.4 orchestration and immutable output storage for one external-discovery source run."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from hawkeye.candidates import generate_external_discovery_candidates
from hawkeye.candidates.normalization import (
    candidate_target_from_hostname,
    hostname_from_observed_url,
)
from hawkeye.discovery.urlscan import ExternalDiscoverySource, UrlscanSearchResponse
from hawkeye.models import (
    CandidateObservation,
    CaseRecord,
    ExternalDiscoveryDocument,
    ExternalDiscoveryEvidenceReference,
    ExternalDiscoveryObservation,
)

_RAW_RESPONSE_PATH = "source-response.json"
_RESPONSE_METADATA_PATH = "source-response.meta.json"
_CANDIDATE_DOCUMENT_PATH = "external-candidates.json"
_CANDIDATE_OBSERVATIONS_PATH = "external-candidate-observations.json"


class ExternalDiscoveryInputError(ValueError):
    """Raised when a local source case or output destination is not eligible for V0.4."""


@dataclass(frozen=True)
class ExternalDiscoveryResult:
    """The persisted document and directory produced by one source strategy invocation."""

    directory: Path
    document: ExternalDiscoveryDocument


def discover_case(
    case_directory: Path | str,
    *,
    output_directory: Path | str,
    source: ExternalDiscoverySource,
    limit: int = 10,
    timeout_seconds: float = 10.0,
) -> ExternalDiscoveryResult:
    """Run exactly one opt-in source and feed its observations through the V0.2 candidate engine."""

    source_root, case, case_json = _load_completed_case(Path(case_directory))
    query_hostname = _query_hostname(case)
    response = source.collect(query_hostname, limit=limit, timeout_seconds=timeout_seconds)
    destination = _create_output_directory(Path(output_directory), source_root)
    raw_path = destination / _RAW_RESPONSE_PATH
    raw_path.write_bytes(response.raw_response)
    evidence = ExternalDiscoveryEvidenceReference(
        id="evidence-external-source-response-001",
        source_name=source.name,
        request_url=response.request_url,
        path=_RAW_RESPONSE_PATH,
        metadata_path=_RESPONSE_METADATA_PATH,
        sha256=hashlib.sha256(response.raw_response).hexdigest(),
        collected_at=response.collected_at,
        collection_mode=response.collection_mode,
        http_status=response.http_status,
        response_bytes=len(response.raw_response),
        result_limit=limit,
    )
    _write_json(
        destination / _RESPONSE_METADATA_PATH,
        _response_metadata(source=source, response=response, evidence=evidence),
    )
    source_observations = _source_candidate_observations(
        case=case,
        response=response,
        evidence=evidence,
        source=source,
    )
    candidate_generation = generate_external_discovery_candidates(
        case=case,
        source_hosts=_known_source_hostnames(case, query_hostname),
        observations=source_observations,
    )
    external_observations = _external_observations(candidate_generation.observations)
    _write_json(
        destination / _CANDIDATE_DOCUMENT_PATH,
        candidate_generation.document.model_dump(mode="json"),
    )
    _write_json(
        destination / _CANDIDATE_OBSERVATIONS_PATH,
        [observation.model_dump(mode="json") for observation in candidate_generation.observations],
    )
    document = ExternalDiscoveryDocument(
        source_name=source.name,
        source_version=source.version,
        source_case_id=case.case_id,
        source_case_json_sha256=hashlib.sha256(case_json).hexdigest(),
        query_hostname=query_hostname,
        source_result_count=len(response.results),
        response_evidence=evidence,
        candidates=candidate_generation.document.candidates,
        observations=external_observations,
        candidate_document_path=_CANDIDATE_DOCUMENT_PATH,
        candidate_observations_path=_CANDIDATE_OBSERVATIONS_PATH,
        excluded_observation_count=candidate_generation.document.excluded_observation_count,
        warnings=list(response.warnings),
        generated_at=datetime.now(UTC),
    )
    _write_json(destination / "external-discovery.json", document.model_dump(mode="json"))
    return ExternalDiscoveryResult(directory=destination, document=document)


def _load_completed_case(directory: Path) -> tuple[Path, CaseRecord, bytes]:
    requested_root = directory.expanduser()
    if requested_root.is_symlink():
        raise ExternalDiscoveryInputError(
            f"External discovery case directory symlink is not allowed: {directory}"
        )
    try:
        root = requested_root.resolve()
    except OSError as error:
        raise ExternalDiscoveryInputError(
            f"Unable to resolve external discovery case directory: {directory}"
        ) from error
    if not root.is_dir():
        raise ExternalDiscoveryInputError(f"Case directory does not exist: {root}")
    case_path = root / "case.json"
    if case_path.is_symlink() or not case_path.is_file():
        raise ExternalDiscoveryInputError(f"Case JSON is not a regular file: {case_path}")
    try:
        case_json = case_path.read_bytes()
        case = CaseRecord.model_validate_json(case_json)
    except (OSError, ValueError) as error:
        raise ExternalDiscoveryInputError(f"Invalid case JSON in {root}: {error}") from error
    if case.status != "completed":
        raise ExternalDiscoveryInputError(f"Case is not completed: {case.case_id}")
    return root, case, case_json


def _query_hostname(case: CaseRecord) -> str:
    query_url = case.final_url or case.seed_url
    hostname = hostname_from_observed_url(query_url)
    if hostname is None:
        raise ExternalDiscoveryInputError(
            f"Completed case has no usable source hostname: {case.case_id}"
        )
    target, exclusion_reason = candidate_target_from_hostname(hostname)
    if target is None:
        raise ExternalDiscoveryInputError(
            "Completed case source hostname is not a public registrable hostname: "
            f"{exclusion_reason}"
        )
    return target.hostname


def _known_source_hostnames(case: CaseRecord, query_hostname: str) -> set[str]:
    """Avoid rediscovering the case seed, safe final host, or stored crawl boundary as a lead."""

    hostnames = {query_hostname}
    for source_url in (case.seed_url, case.final_url):
        if source_url is None:
            continue
        hostname = hostname_from_observed_url(source_url)
        if hostname is not None:
            hostnames.add(hostname)
    for allowed_host in case.allowed_crawl_hosts:
        target, _ = candidate_target_from_hostname(allowed_host)
        if target is not None:
            hostnames.add(target.hostname)
    return hostnames


def _create_output_directory(destination: Path, case_root: Path) -> Path:
    try:
        output = destination.expanduser().resolve()
    except OSError as error:
        raise ExternalDiscoveryInputError(
            f"Unable to resolve external discovery output directory: {destination}"
        ) from error
    if output == case_root or case_root in output.parents:
        raise ExternalDiscoveryInputError(
            "External discovery output must not be written inside the source case directory"
        )
    if output.exists():
        raise FileExistsError(f"External discovery output already exists: {output}")
    try:
        output.mkdir(parents=True)
    except OSError as error:
        raise ExternalDiscoveryInputError(
            f"Unable to create external discovery output directory: {output}"
        ) from error
    return output


def _response_metadata(
    *,
    source: ExternalDiscoverySource,
    response: UrlscanSearchResponse,
    evidence: ExternalDiscoveryEvidenceReference,
) -> dict[str, Any]:
    """Persist source-contract metadata so raw bytes remain replayable and inspectable."""

    return {
        "source_name": source.name,
        "source_version": source.version,
        "request_url": response.request_url,
        "retrieved_at": response.collected_at.isoformat(),
        "collection_mode": response.collection_mode,
        "http_status": response.http_status,
        "content_type": evidence.content_type,
        "response_bytes": evidence.response_bytes,
        "response_sha256": evidence.sha256,
        "result_limit": evidence.result_limit,
        "evaluated_result_count": len(response.results),
    }


def _source_candidate_observations(
    *,
    case: CaseRecord,
    response: UrlscanSearchResponse,
    evidence: ExternalDiscoveryEvidenceReference,
    source: ExternalDiscoverySource,
) -> list[CandidateObservation]:
    observations: list[CandidateObservation] = []
    number = 0
    for index, result in enumerate(response.results, start=1):
        result_id = _source_result_id(result, index)
        for source_field, observed_url in _result_urls(result):
            number += 1
            observations.append(
                CandidateObservation(
                    id=f"external-candidate-observation-{number:04d}",
                    observation_type="external_discovery",
                    source_case_id=case.case_id,
                    source_evidence_id=evidence.id,
                    source_url=response.request_url,
                    target_url=observed_url,
                    target_host=hostname_from_observed_url(observed_url),
                    direction="source_to_candidate",
                    discovery_method="public_source",
                    candidate_decision="excluded",
                    exclusion_reason="not_evaluated",
                    details={
                        "source_adapter": source.name,
                        "source_adapter_version": source.version,
                        "source_result_id": result_id,
                        "source_field": source_field,
                        "response_path": evidence.path,
                        "response_sha256": evidence.sha256,
                    },
                )
            )
    return observations


def _external_observations(
    observations: list[CandidateObservation],
) -> list[ExternalDiscoveryObservation]:
    output: list[ExternalDiscoveryObservation] = []
    for observation in observations:
        source_field = observation.details.get("source_field")
        source_result_id = observation.details.get("source_result_id")
        if (
            source_field not in {"task_url", "page_url"}
            or source_result_id is None
            or observation.target_url is None
            or observation.source_evidence_id is None
        ):
            raise ExternalDiscoveryInputError(
                "External discovery candidate observation lost required source provenance"
            )
        output.append(
            ExternalDiscoveryObservation(
                id=observation.id,
                source_name="urlscan_public",
                source_result_id=source_result_id,
                source_field=cast(Literal["task_url", "page_url"], source_field),
                observed_url=observation.target_url,
                target_host=observation.target_host,
                candidate_decision=observation.candidate_decision,
                exclusion_reason=observation.exclusion_reason,
                evidence_id=observation.source_evidence_id,
                candidate_observation_id=observation.id,
            )
        )
    return output


def _source_result_id(result: dict[str, Any], index: int) -> str:
    task = result.get("task")
    if isinstance(task, dict):
        raw_identifier = task.get("uuid")
        if isinstance(raw_identifier, str) and raw_identifier.strip():
            return raw_identifier.strip()
    return f"result-{index:04d}"


def _result_urls(
    result: dict[str, Any],
) -> list[tuple[Literal["task_url", "page_url"], str]]:
    observed: list[tuple[Literal["task_url", "page_url"], str]] = []
    task = result.get("task")
    if isinstance(task, dict) and isinstance(task.get("url"), str):
        observed.append(("task_url", task["url"]))
    page = result.get("page")
    if isinstance(page, dict) and isinstance(page.get("url"), str):
        observed.append(("page_url", page["url"]))
    return observed


def _write_json(path: Path, payload: Any) -> None:
    serialized = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    path.write_text(f"{serialized}\n", encoding="utf-8")
