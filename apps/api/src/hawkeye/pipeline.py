"""Bounded evidence collection, same-site crawling, and V0.2 candidate generation."""

from __future__ import annotations

import hashlib
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from io import BytesIO
from pathlib import Path
from time import monotonic

from PIL import Image

from hawkeye.candidates import CandidateGeneration, generate_candidates
from hawkeye.classification import classify_capture, derive_public_status
from hawkeye.collector.playwright_collector import (
    DEFAULT_MAX_DECLARED_RESPONSE_BYTES,
    DEFAULT_MAX_TOTAL_REQUESTS,
    DEFAULT_USER_AGENT,
    DIRECT_EXTRACTOR_LIMIT_BYTES,
    BrowserCollector,
    CollectionBudget,
    CollectionError,
)
from hawkeye.collector.safety import SafetyPolicy, UnsafeUrlError
from hawkeye.crawl import (
    DEFAULT_MAX_HTML_BYTES,
    MAX_CASE_TIMEOUT_SECONDS,
    MAX_CRAWL_DEPTH,
    MAX_CRAWL_PAGES,
    MAX_PAGE_TIMEOUT_SECONDS,
    DiscoveredLink,
    crawl_frontier_priority,
    crawl_hostname,
    discover_anchor_links,
    normalize_crawl_url,
)
from hawkeye.extraction import extract_entities
from hawkeye.graph import build_graph
from hawkeye.models import (
    CaptureAdequacy,
    CaseRecord,
    CrawlConfiguration,
    CrawlFrontierRecord,
    CrawlPageRecord,
    EvidenceRecord,
    ExtractedEntity,
    InvestigationResult,
    RedirectRecord,
    SemanticElementSnapshot,
    SemanticObservation,
)
from hawkeye.ocr import run_bounded_ocr
from hawkeye.semantic_evidence import extract_semantic_observations
from hawkeye.storage import CaseStorage, make_case_id

MAX_DISCOVERED_LINKS_PER_PAGE = 200
ProgressCallback = Callable[[str, dict[str, object]], None]


@dataclass(frozen=True)
class _CrawlTarget:
    """A queued page id together with the frontier event that created it."""

    page_id: str
    frontier_id: str


def investigate(
    seed_url: str,
    *,
    output: Path | str = Path("cases"),
    timeout_seconds: float = 30.0,
    case_timeout_seconds: float = MAX_CASE_TIMEOUT_SECONDS,
    max_pages: int = MAX_CRAWL_PAGES,
    max_depth: int = MAX_CRAWL_DEPTH,
    max_html_bytes: int = DEFAULT_MAX_HTML_BYTES,
    max_total_requests: int = DEFAULT_MAX_TOTAL_REQUESTS,
    max_declared_response_bytes: int = DEFAULT_MAX_DECLARED_RESPONSE_BYTES,
    headed: bool = False,
    case_id: str | None = None,
    max_redirects: int = 5,
    user_agent: str | None = None,
    safety_policy: SafetyPolicy | None = None,
    corpus_root: Path | str | None = None,
    enable_ocr: bool = False,
    ocr_executable: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> InvestigationResult:
    """Collect a seed plus a deterministic, same-host, depth-one BFS frontier.

    The crawl is intentionally fixed at no more than five HTML pages, depth one, a single
    synchronous browser page at a time, and an overall two-minute case budget. It never clicks,
    submits forms, or follows external navigation targets. A failed child is persisted and does
    not stop later queued children. After collection, V0.2 produces local evidence-based pending
    candidates only; candidates are never automatically navigated.
    """

    _validate_crawl_limits(
        timeout_seconds=timeout_seconds,
        case_timeout_seconds=case_timeout_seconds,
        max_pages=max_pages,
        max_depth=max_depth,
        max_html_bytes=max_html_bytes,
        max_total_requests=max_total_requests,
        max_declared_response_bytes=max_declared_response_bytes,
        max_redirects=max_redirects,
    )
    safety = safety_policy or SafetyPolicy()
    _emit_progress(progress_callback, "validating_seed", seed_url=seed_url)
    validated_seed = safety.validate_crawl_url(seed_url)
    normalized_seed = validated_seed.normalized_url
    chosen_case_id = case_id or make_case_id()
    storage = CaseStorage.create(Path(output), chosen_case_id)
    started_at = datetime.now(UTC)
    configuration = CrawlConfiguration(
        max_depth=max_depth,
        max_pages_total=max_pages,
        max_redirects_per_page=max_redirects,
        page_timeout_seconds=timeout_seconds,
        case_timeout_seconds=case_timeout_seconds,
        max_html_bytes=max_html_bytes,
        max_total_requests=max_total_requests,
        max_declared_response_bytes=max_declared_response_bytes,
        allowed_crawl_hosts=[validated_seed.hostname],
    )
    case = CaseRecord(
        case_id=chosen_case_id,
        seed_url=normalized_seed,
        status="running",
        started_at=started_at,
        crawl_configuration=configuration,
        allowed_crawl_hosts=[validated_seed.hostname],
    )
    pages = [
        CrawlPageRecord(
            id="page-001",
            url=normalized_seed,
            normalized_url=normalized_seed,
            depth=0,
            state="queued",
            discovery_method="seed",
        )
    ]
    frontier = [
        CrawlFrontierRecord(
            id="frontier-0001",
            depth=0,
            state="queued",
            normalized_url=normalized_seed,
            discovery_method="seed",
            target_page_id="page-001",
        )
    ]
    evidence: list[EvidenceRecord] = []
    entities: list[ExtractedEntity] = []
    observations: list[SemanticObservation] = []
    queue: deque[_CrawlTarget] = deque([_CrawlTarget("page-001", "frontier-0001")])
    known_urls = {normalized_seed}
    allowed_hosts = {validated_seed.hostname}
    content_hashes: dict[str, str] = {}
    traffic_budget = CollectionBudget(
        max_total_requests=max_total_requests,
        max_declared_response_bytes=max_declared_response_bytes,
    )
    deadline = monotonic() + case_timeout_seconds

    storage.write_json("case.json", case.model_dump(mode="json"))
    storage.log(f"case_started seed_url={normalized_seed}")
    _emit_progress(
        progress_callback,
        "initializing_case",
        case_id=chosen_case_id,
        max_pages=max_pages,
        max_depth=max_depth,
    )

    while queue:
        target = queue.popleft()
        current = _page_by_id(pages, target.page_id)
        if traffic_budget.exhausted_reason is not None:
            _replace_page(
                pages,
                target.page_id,
                state="skipped",
                skip_reason=traffic_budget.exhausted_reason,
                error="Shared browser traffic budget exhausted before navigation",
            )
            _replace_frontier(
                frontier,
                target.frontier_id,
                state="skipped",
                skip_reason=traffic_budget.exhausted_reason,
            )
            storage.log(
                f"page_skipped page_id={target.page_id} reason={traffic_budget.exhausted_reason}"
            )
            continue
        remaining = deadline - monotonic()
        if remaining <= 0:
            _replace_page(
                pages,
                target.page_id,
                state="skipped",
                skip_reason="case_timeout",
                error="Overall case timeout reached before navigation",
            )
            _replace_frontier(
                frontier,
                target.frontier_id,
                state="skipped",
                skip_reason="case_timeout",
            )
            storage.log(f"page_skipped page_id={target.page_id} reason=case_timeout")
            continue

        _replace_page(pages, target.page_id, state="visiting")
        _replace_frontier(frontier, target.frontier_id, state="visiting")
        _emit_progress(
            progress_callback,
            "capturing_page",
            page_id=current.id,
            depth=current.depth,
            queued_pages=len(queue),
        )
        page_timeout = min(timeout_seconds, remaining)
        try:
            collector = BrowserCollector(
                safety=safety,
                timeout_seconds=page_timeout,
                max_redirects=max_redirects,
                max_html_bytes=max_html_bytes,
                budget=traffic_budget,
                allowed_navigation_hosts=(None if current.depth == 0 else sorted(allowed_hosts)),
                headed=headed,
                user_agent=user_agent or DEFAULT_USER_AGENT,
            )
            collected = collector.collect(current.normalized_url)
        except Exception as error:  # Child failures must be recorded and not stop the frontier.
            redirect_evidence_id = _save_redirect_observations(
                storage=storage,
                evidence=evidence,
                page=current,
                error=error,
            )
            _record_collection_failure(
                pages,
                frontier,
                target,
                error,
                redirect_evidence_id=redirect_evidence_id,
            )
            if redirect_evidence_id is not None:
                _record_blocked_redirect_destinations(
                    frontier=frontier,
                    page=current,
                    error=error,
                    redirect_evidence_id=redirect_evidence_id,
                )
            storage.log(
                "page_failed "
                f"page_id={target.page_id} reason={_failure_reason(error)} error={error}"
            )
            if current.depth == 0:
                break
            continue

        _emit_progress(
            progress_callback,
            "preserving_artifacts",
            page_id=current.id,
            final_url=collected.final_url,
        )

        if current.depth == 0:
            final_hostname = crawl_hostname(collected.final_url)
            if final_hostname is None:
                _record_collection_failure(
                    pages,
                    frontier,
                    target,
                    CollectionError("Collected final URL has no hostname"),
                )
                storage.log(f"page_failed page_id={target.page_id} reason=navigation_error")
                break
            allowed_hosts.add(final_hostname)
        canonical_page_url = normalize_crawl_url(collected.final_url, collected.final_url)
        if canonical_page_url is not None:
            known_urls.add(canonical_page_url)

        redirect_evidence_id = _save_redirect_records(
            storage=storage,
            evidence=evidence,
            page=current,
            redirects=collected.redirects,
        )
        readiness = collected.readiness
        if readiness is None:
            raise RuntimeError("Collector did not return capture-readiness evidence")
        html_evidence = (
            storage.save_html(
                collected.html,
                source_url=collected.final_url,
                collected_at=collected.collected_at,
                page_id=current.id,
            )
            if collected.html_persistable
            else None
        )
        screenshot_evidence = storage.save_screenshot(
            collected.screenshot,
            source_url=collected.final_url,
            collected_at=collected.collected_at,
            viewport=collected.viewport,
            image_dimensions=collected.image_dimensions,
            page_id=current.id,
        )
        _emit_progress(
            progress_callback,
            "page_preview_ready",
            case_id=chosen_case_id,
            page_id=current.id,
            url=collected.final_url,
            captured_at=collected.collected_at.isoformat(),
            width=collected.image_dimensions["width"],
            height=collected.image_dimensions["height"],
            sha256=hashlib.sha256(collected.screenshot).hexdigest(),
        )
        visible_text_evidence = storage.save_capture_text(
            collected.visible_text,
            source_url=collected.final_url,
            collected_at=collected.collected_at,
            page_id=current.id,
        )
        response_metadata_evidence = storage.save_capture_json(
            {
                "status": readiness.response_status,
                "url": readiness.response_url,
                "headers": readiness.response_headers,
                "content_type": readiness.content_type,
                "redirects": [record.model_dump(mode="json") for record in collected.redirects],
            },
            artifact_kind="response_metadata",
            source_url=collected.final_url,
            collected_at=collected.collected_at,
            page_id=current.id,
        )
        readiness_evidence = storage.save_capture_json(
            readiness.model_dump(mode="json"),
            artifact_kind="capture_readiness",
            source_url=collected.final_url,
            collected_at=collected.collected_at,
            page_id=current.id,
        )
        initial_screenshot_evidence = None
        if (
            collected.initial_screenshot is not None
            and collected.initial_image_dimensions is not None
        ):
            initial_screenshot_evidence = storage.save_screenshot(
                collected.initial_screenshot,
                source_url=collected.final_url,
                collected_at=readiness.checkpoints[0].captured_at,
                viewport=collected.viewport,
                image_dimensions=collected.initial_image_dimensions,
                page_id=current.id,
                artifact_kind="initial_screenshot",
            )
        full_page_screenshot_evidence = None
        if (
            collected.full_page_screenshot is not None
            and collected.full_page_image_dimensions is not None
        ):
            full_page_screenshot_evidence = storage.save_screenshot(
                collected.full_page_screenshot,
                source_url=collected.final_url,
                collected_at=collected.collected_at,
                viewport=collected.viewport,
                image_dimensions=collected.full_page_image_dimensions,
                page_id=current.id,
                artifact_kind="full_page_screenshot",
            )
        evidence.extend(
            record
            for record in (
                html_evidence,
                screenshot_evidence,
                initial_screenshot_evidence,
                full_page_screenshot_evidence,
                visible_text_evidence,
                response_metadata_evidence,
                readiness_evidence,
            )
            if record is not None
        )
        ocr_text_evidence = None
        ocr_result = None
        ocr_metadata_evidence = None
        if enable_ocr:
            _emit_progress(progress_callback, "running_ocr", page_id=current.id)
            ocr_source = collected.full_page_screenshot or collected.screenshot
            ocr_result = run_bounded_ocr(ocr_source, executable=ocr_executable)
            ocr_metadata_evidence = storage.save_ocr_metadata(
                ocr_result.model_dump(mode="json"),
                source_url=collected.final_url,
                collected_at=collected.collected_at,
                page_id=current.id,
            )
            evidence.append(ocr_metadata_evidence)
            if ocr_result.status == "completed" and ocr_result.text:
                ocr_text_evidence = storage.save_ocr_text(
                    ocr_result.text,
                    source_url=collected.final_url,
                    collected_at=collected.collected_at,
                    page_id=current.id,
                )
                evidence.append(ocr_text_evidence)
        classification = classify_capture(
            title=collected.title,
            final_url=collected.final_url,
            visible_text=collected.visible_text,
            navigation_status="captured",
        )
        verified_extraction = bool(
            classification.content_usable
            and classification.access_outcome is not None
            and classification.access_outcome.value == "content"
            and readiness.capture_adequacy is CaptureAdequacy.ADEQUATE
            and html_evidence is not None
            and readiness.html_bytes <= DIRECT_EXTRACTOR_LIMIT_BYTES
        )
        provisional_extraction = bool(
            classification.content_usable
            and classification.access_outcome is not None
            and classification.access_outcome.value == "content"
            and readiness.capture_adequacy is CaptureAdequacy.LIMITED
            and html_evidence is not None
            and readiness.html_bytes <= DIRECT_EXTRACTOR_LIMIT_BYTES
            and readiness.checkpoints
            and readiness.checkpoints[-1].visible_text_chars >= 80
            and (
                readiness.checkpoints[-1].informative_tile_ratio >= 0.02
                or readiness.checkpoints[-1].visible_text_words >= 15
            )
            and "visual_dom_mismatch" not in readiness.limitation_reasons
            and "low_information_capture" not in readiness.limitation_reasons
        )
        extraction_eligible = verified_extraction or provisional_extraction
        extraction_tier = (
            "verified"
            if verified_extraction
            else "provisional"
            if provisional_extraction
            else "none"
        )
        extraction_skip_reason = None
        if not extraction_eligible:
            if (
                classification.access_outcome is None
                or classification.access_outcome.value != "content"
            ):
                extraction_skip_reason = "access_outcome_is_not_content"
            elif html_evidence is None:
                extraction_skip_reason = "canonical_html_not_persisted"
            elif readiness.html_bytes > DIRECT_EXTRACTOR_LIMIT_BYTES:
                extraction_skip_reason = "direct_extractor_input_exceeds_2_mb"
            elif readiness.capture_adequacy is not CaptureAdequacy.ADEQUATE:
                extraction_skip_reason = "capture_adequacy_is_not_adequate"
        public_status = derive_public_status(
            navigation_status="captured",
            access_outcome=classification.access_outcome,
            capture_adequacy=readiness.capture_adequacy,
        )
        page_entities: list[ExtractedEntity] = []
        if extraction_eligible and html_evidence is not None:
            _emit_progress(progress_callback, "extracting_evidence", page_id=current.id)
            page_entities = extract_entities(
                collected.html,
                seed_url=normalized_seed,
                final_url=collected.final_url,
                source_evidence_id=html_evidence.id,
                entity_id_start=len(entities) + 1,
            )
            if provisional_extraction:
                page_entities = [
                    item.model_copy(
                        update={
                            "confidence": min(item.confidence, 0.85),
                            "details": {
                                **item.details,
                                "evidence_tier": "provisional",
                                "source_capture_adequacy": readiness.capture_adequacy.value,
                            },
                        }
                    )
                    for item in page_entities
                ]
            entities.extend(page_entities)
            page_observations = extract_semantic_observations(
                collected.html,
                source_page_id=current.id,
                source_url=collected.final_url,
                source_artifact_id=html_evidence.id,
                screenshot_evidence_id=screenshot_evidence.id,
                semantic_elements=[
                    item
                    for item in collected.semantic_elements
                    if item.source_context == "document"
                ],
                redirects=collected.redirects,
                observation_id_start=len(observations) + 1,
            )
            if provisional_extraction:
                page_observations = [
                    item.model_copy(
                        update={
                            "confidence": min(item.confidence, 0.85),
                            "limitations": [
                                *item.limitations,
                                "provisional_observation_from_limited_capture",
                                *readiness.limitation_reasons,
                            ],
                            "attributes": {
                                **item.attributes,
                                "provisional": True,
                                "source_capture_adequacy": readiness.capture_adequacy.value,
                            },
                        }
                    )
                    for item in page_observations
                ]
            observations.extend(
                _attach_observation_crops(
                    storage=storage,
                    observations=page_observations,
                    screenshot=collected.screenshot,
                    collected_at=collected.collected_at,
                    evidence=evidence,
                )
            )

        if ocr_text_evidence is not None and ocr_result is not None:
            ocr_html = f"<main>{escape(ocr_result.text)}</main>"
            ocr_entities = extract_entities(
                ocr_html,
                seed_url=normalized_seed,
                final_url=collected.final_url,
                source_evidence_id=ocr_text_evidence.id,
                entity_id_start=len(entities) + 1,
            )
            entities.extend(
                item.model_copy(
                    update={
                        "confidence": min(item.confidence, 0.72),
                        "extraction_method": f"ocr_{item.extraction_method}",
                        "details": {
                            **item.details,
                            "evidence_tier": "provisional",
                            "ocr_engine": ocr_result.engine,
                        },
                    }
                )
                for item in ocr_entities
            )
            ocr_observations = extract_semantic_observations(
                ocr_html,
                source_page_id=current.id,
                source_url=collected.final_url,
                source_artifact_id=ocr_text_evidence.id,
                screenshot_evidence_id=screenshot_evidence.id,
                semantic_elements=[],
                redirects=[],
                observation_id_start=len(observations) + 1,
            )
            observations.extend(
                item.model_copy(
                    update={
                        "confidence": min(item.confidence, 0.72),
                        "limitations": [
                            *item.limitations,
                            "provisional_observation_from_local_ocr",
                            "ocr_text_requires_human_visual_confirmation",
                        ],
                        "attributes": {
                            **item.attributes,
                            "provisional": True,
                            "extraction_method": "tesseract_local_ocr",
                        },
                    }
                )
                for item in ocr_observations
            )

        content_sha256 = readiness.html_sha256
        duplicate_of = content_hashes.get(content_sha256)
        if duplicate_of is None:
            content_hashes[content_sha256] = current.id
        completion_reason = "duplicate_content" if duplicate_of else None
        _replace_page(
            pages,
            target.page_id,
            state="completed",
            final_url=collected.final_url,
            redirects=collected.redirects,
            navigation_status="captured",
            capture_outcome=classification.outcome,
            content_usable=classification.content_usable,
            access_outcome=classification.access_outcome,
            capture_adequacy=readiness.capture_adequacy,
            extraction_eligible=extraction_eligible,
            extraction_tier=extraction_tier,
            extraction_skip_reason=extraction_skip_reason,
            public_status=public_status,
            limitation_reasons=readiness.limitation_reasons,
            classification_reasons=classification.reasons,
            page_title=collected.title,
            html_evidence_id=html_evidence.id if html_evidence is not None else None,
            screenshot_evidence_id=screenshot_evidence.id,
            initial_screenshot_evidence_id=(
                initial_screenshot_evidence.id if initial_screenshot_evidence else None
            ),
            full_page_screenshot_evidence_id=(
                full_page_screenshot_evidence.id if full_page_screenshot_evidence else None
            ),
            ocr_text_evidence_id=(ocr_text_evidence.id if ocr_text_evidence else None),
            ocr_metadata_evidence_id=(ocr_metadata_evidence.id if ocr_metadata_evidence else None),
            visible_text_evidence_id=visible_text_evidence.id,
            response_metadata_evidence_id=response_metadata_evidence.id,
            readiness_evidence_id=readiness_evidence.id,
            redirect_evidence_id=redirect_evidence_id,
            content_sha256=content_sha256,
            content_type=collected.content_type,
            blocked_requests=collected.blocked_requests,
            blocked_popup_count=collected.blocked_popup_count,
            blocked_download_count=collected.blocked_download_count,
            duplicate_of_page_id=duplicate_of,
            skip_reason=completion_reason,
            error=None,
        )
        _replace_frontier(
            frontier,
            target.frontier_id,
            state="completed",
            skip_reason=completion_reason,
        )
        storage.log(
            "page_completed "
            f"page_id={target.page_id} depth={current.depth} "
            f"outcome={classification.outcome.value} "
            f"adequacy={readiness.capture_adequacy.value} "
            f"eligible={extraction_eligible} tier={extraction_tier} entities={len(page_entities)}"
        )
        _emit_progress(
            progress_callback,
            "page_completed",
            page_id=current.id,
            adequacy=readiness.capture_adequacy.value,
            observations=len(observations),
        )

        completed_page = _page_by_id(pages, target.page_id)
        if (
            extraction_eligible
            and duplicate_of is None
            and completed_page.depth < max_depth
            and html_evidence is not None
        ):
            _enqueue_discovered_links(
                html=collected.html,
                semantic_elements=collected.semantic_elements,
                parent=completed_page,
                parent_evidence_id=html_evidence.id,
                allowed_hosts=allowed_hosts,
                known_urls=known_urls,
                safety=safety,
                pages=pages,
                frontier=frontier,
                queue=queue,
                max_pages=max_pages,
                max_depth=max_depth,
            )
        else:
            reason = (
                "unusable_parent_page"
                if not classification.content_usable
                else "extraction_ineligible_parent_page"
                if not extraction_eligible
                else "duplicate_content"
                if duplicate_of is not None
                else "depth_limit"
            )
            if html_evidence is not None:
                _record_nonexpanded_links(
                    html=collected.html,
                    semantic_elements=collected.semantic_elements,
                    parent=completed_page,
                    parent_evidence_id=html_evidence.id,
                    reason=reason,
                    frontier=frontier,
                )

    primary = pages[0]
    case_status = "completed" if primary.state == "completed" else "failed"
    completed_case = case.model_copy(
        update={
            "status": case_status,
            "completed_at": datetime.now(UTC),
            "final_url": primary.final_url,
            "redirect_chain": [record.source_url for record in primary.redirects],
            "redirects": primary.redirects,
            "navigation_status": primary.navigation_status,
            "capture_outcome": primary.capture_outcome,
            "content_usable": primary.content_usable,
            "access_outcome": primary.access_outcome,
            "capture_adequacy": primary.capture_adequacy,
            "extraction_eligible": primary.extraction_eligible,
            "extraction_tier": primary.extraction_tier,
            "extraction_skip_reason": primary.extraction_skip_reason,
            "public_status": primary.public_status,
            "limitation_reasons": primary.limitation_reasons,
            "classification_reasons": primary.classification_reasons,
            "page_title": primary.page_title,
            "page_count": sum(page.state == "completed" for page in pages),
            "crawl_configuration": configuration.model_copy(
                update={"allowed_crawl_hosts": sorted(allowed_hosts)}
            ),
            "allowed_crawl_hosts": sorted(allowed_hosts),
            "total_request_count": traffic_budget.request_count,
            "total_declared_response_bytes": traffic_budget.declared_response_bytes,
            "budget_exhausted_reason": traffic_budget.exhausted_reason,
            "error": primary.error if case_status == "failed" else None,
        }
    )
    selected_corpus_root = (
        Path(corpus_root).expanduser().resolve() if corpus_root is not None else storage.root.parent
    )
    _emit_progress(
        progress_callback,
        "generating_candidates",
        page_count=completed_case.page_count,
        observation_count=len(observations),
    )
    candidate_generation = generate_candidates(
        case=completed_case,
        pages=pages,
        evidence=evidence,
        entities=entities,
        frontier=frontier,
        corpus_root=selected_corpus_root,
        current_case_directory=storage.root,
    )
    completed_case = completed_case.model_copy(
        update={"candidate_count": len(candidate_generation.document.candidates)}
    )
    _write_case_outputs(
        storage=storage,
        case=completed_case,
        pages=pages,
        frontier=frontier,
        evidence=evidence,
        entities=entities,
        observations=observations,
        candidate_generation=candidate_generation,
    )
    _emit_progress(
        progress_callback,
        "finalizing_case",
        status=completed_case.status,
        page_count=completed_case.page_count,
        candidate_count=len(candidate_generation.document.candidates),
    )
    storage.log(
        "case_completed "
        f"status={completed_case.status} pages={completed_case.page_count} "
        f"frontier={len(frontier)} entities={len(entities)}"
    )
    return InvestigationResult(
        case_directory=str(storage.root),
        case=completed_case,
        pages=pages,
        frontier=frontier,
        candidates=candidate_generation.document.candidates,
        observations=observations,
    )


def _emit_progress(
    callback: ProgressCallback | None,
    stage: str,
    **detail: object,
) -> None:
    if callback is not None:
        callback(stage, detail)


def _validate_crawl_limits(
    *,
    timeout_seconds: float,
    case_timeout_seconds: float,
    max_pages: int,
    max_depth: int,
    max_html_bytes: int,
    max_total_requests: int,
    max_declared_response_bytes: int,
    max_redirects: int,
) -> None:
    if not 0 < timeout_seconds <= MAX_PAGE_TIMEOUT_SECONDS:
        raise ValueError(
            f"timeout_seconds must be greater than zero and at most {MAX_PAGE_TIMEOUT_SECONDS}"
        )
    if not 0 < case_timeout_seconds <= MAX_CASE_TIMEOUT_SECONDS:
        raise ValueError(
            f"case_timeout_seconds must be greater than zero and at most {MAX_CASE_TIMEOUT_SECONDS}"
        )
    if not 1 <= max_pages <= MAX_CRAWL_PAGES:
        raise ValueError(f"max_pages must be between one and {MAX_CRAWL_PAGES}")
    if not 0 <= max_depth <= MAX_CRAWL_DEPTH:
        raise ValueError(f"max_depth must be between zero and {MAX_CRAWL_DEPTH}")
    if max_html_bytes <= 0:
        raise ValueError("max_html_bytes must be positive")
    if not 1 <= max_total_requests <= DEFAULT_MAX_TOTAL_REQUESTS:
        raise ValueError(f"max_total_requests must be between one and {DEFAULT_MAX_TOTAL_REQUESTS}")
    if not 1 <= max_declared_response_bytes <= DEFAULT_MAX_DECLARED_RESPONSE_BYTES:
        raise ValueError(
            "max_declared_response_bytes must be between one and "
            f"{DEFAULT_MAX_DECLARED_RESPONSE_BYTES}"
        )
    if not 0 <= max_redirects <= 5:
        raise ValueError("max_redirects must be between zero and five")


def _enqueue_discovered_links(
    *,
    html: str,
    semantic_elements: Iterable[SemanticElementSnapshot],
    parent: CrawlPageRecord,
    parent_evidence_id: str,
    allowed_hosts: set[str],
    known_urls: set[str],
    safety: SafetyPolicy,
    pages: list[CrawlPageRecord],
    frontier: list[CrawlFrontierRecord],
    queue: deque[_CrawlTarget],
    max_pages: int,
    max_depth: int,
) -> None:
    for index, link in enumerate(
        _sorted_links(html, parent.final_url or parent.normalized_url, semantic_elements), start=1
    ):
        frontier_id = _next_frontier_id(frontier)
        priority_score, priority_reason = crawl_frontier_priority(link)
        record = CrawlFrontierRecord(
            id=frontier_id,
            depth=parent.depth + 1,
            state="discovered",
            original_href=link.original_href,
            normalized_url=link.normalized_url,
            source_page_id=parent.id,
            source_evidence_id=parent_evidence_id,
            discovery_method=link.discovery_method,
            anchor_text=link.anchor_text or None,
            priority_score=priority_score,
            priority_reason=priority_reason,
        )
        frontier.append(record)
        if index > MAX_DISCOVERED_LINKS_PER_PAGE:
            _replace_frontier(frontier, frontier_id, state="skipped", skip_reason="frontier_limit")
            continue
        if link.normalized_url is None:
            _replace_frontier(frontier, frontier_id, state="skipped", skip_reason="malformed_url")
            continue
        if parent.depth + 1 > max_depth:
            _replace_frontier(frontier, frontier_id, state="skipped", skip_reason="depth_limit")
            continue
        hostname = crawl_hostname(link.normalized_url)
        if hostname is None:
            _replace_frontier(frontier, frontier_id, state="skipped", skip_reason="malformed_url")
            continue
        if hostname not in allowed_hosts:
            _replace_frontier(frontier, frontier_id, state="skipped", skip_reason="external_host")
            continue
        if link.normalized_url in known_urls:
            _replace_frontier(frontier, frontier_id, state="skipped", skip_reason="duplicate_url")
            continue
        try:
            validated = safety.validate_crawl_url(link.normalized_url)
        except UnsafeUrlError:
            _replace_frontier(
                frontier, frontier_id, state="skipped", skip_reason="unsafe_destination"
            )
            continue
        if len(pages) >= max_pages:
            _replace_frontier(frontier, frontier_id, state="skipped", skip_reason="page_budget")
            continue

        normalized_url = validated.normalized_url
        known_urls.add(normalized_url)
        page_id = _next_page_id(pages)
        pages.append(
            CrawlPageRecord(
                id=page_id,
                url=link.normalized_url,
                normalized_url=normalized_url,
                depth=parent.depth + 1,
                state="queued",
                parent_page_id=parent.id,
                source_evidence_id=parent_evidence_id,
                original_href=link.original_href,
                discovery_method=link.discovery_method,
                anchor_text=link.anchor_text or None,
            )
        )
        _replace_frontier(frontier, frontier_id, state="queued", target_page_id=page_id)
        queue.append(_CrawlTarget(page_id=page_id, frontier_id=frontier_id))


def _record_nonexpanded_links(
    *,
    html: str,
    semantic_elements: Iterable[SemanticElementSnapshot],
    parent: CrawlPageRecord,
    parent_evidence_id: str,
    reason: str,
    frontier: list[CrawlFrontierRecord],
) -> None:
    """Keep link observations auditable when policy deliberately prevents expansion."""

    for index, link in enumerate(
        _sorted_links(html, parent.final_url or parent.normalized_url, semantic_elements), start=1
    ):
        priority_score, priority_reason = crawl_frontier_priority(link)
        frontier.append(
            CrawlFrontierRecord(
                id=_next_frontier_id(frontier),
                depth=parent.depth + 1,
                state="skipped",
                original_href=link.original_href,
                normalized_url=link.normalized_url,
                source_page_id=parent.id,
                source_evidence_id=parent_evidence_id,
                discovery_method=link.discovery_method,
                anchor_text=link.anchor_text or None,
                priority_score=priority_score,
                priority_reason=priority_reason,
                skip_reason=reason if index <= MAX_DISCOVERED_LINKS_PER_PAGE else "frontier_limit",
            )
        )


def _sorted_links(
    html: str,
    base_url: str,
    semantic_elements: Iterable[SemanticElementSnapshot] = (),
) -> list[DiscoveredLink]:
    links = discover_anchor_links(html, base_url)
    for item in semantic_elements:
        href = getattr(item, "href", None)
        context = getattr(item, "source_context", "document")
        if not isinstance(href, str) or context == "document":
            continue
        label = getattr(item, "accessible_name", "") or getattr(item, "visible_text", "")
        links.append(
            DiscoveredLink(
                original_href=href,
                normalized_url=normalize_crawl_url(href, base_url),
                anchor_text=str(label)[:500],
                discovery_method="browser_semantic",
            )
        )
    deduplicated = {
        (item.original_href, item.normalized_url, item.anchor_text, item.discovery_method): item
        for item in links
    }
    return sorted(
        deduplicated.values(),
        key=lambda link: (
            crawl_frontier_priority(link)[0],
            link.normalized_url is None,
            link.normalized_url or "",
            link.original_href,
            link.anchor_text,
        ),
    )


def _save_redirect_observations(
    *,
    storage: CaseStorage,
    evidence: list[EvidenceRecord],
    page: CrawlPageRecord,
    error: Exception,
) -> str | None:
    if not isinstance(error, CollectionError) or not error.redirects:
        return None
    return _save_redirect_records(
        storage=storage,
        evidence=evidence,
        page=page,
        redirects=error.redirects,
    )


def _save_redirect_records(
    *,
    storage: CaseStorage,
    evidence: list[EvidenceRecord],
    page: CrawlPageRecord,
    redirects: list[RedirectRecord],
) -> str | None:
    """Persist every observed document redirect as network evidence for later candidate review."""

    if not redirects:
        return None
    redirect_evidence = storage.save_network_event(
        [record.model_dump(mode="json") for record in redirects],
        source_url=page.normalized_url,
        collected_at=datetime.now(UTC),
        page_id=page.id,
    )
    evidence.append(redirect_evidence)
    return redirect_evidence.id


def _record_blocked_redirect_destinations(
    *,
    frontier: list[CrawlFrontierRecord],
    page: CrawlPageRecord,
    error: Exception,
    redirect_evidence_id: str,
) -> None:
    """Keep blocked redirect targets available to V0.2 without ever navigating them."""

    if not isinstance(error, CollectionError):
        return
    for redirect in error.redirects:
        normalized_target = normalize_crawl_url(redirect.destination_url, redirect.source_url)
        frontier.append(
            CrawlFrontierRecord(
                id=_next_frontier_id(frontier),
                depth=page.depth,
                state="skipped",
                original_href=redirect.destination_url,
                normalized_url=normalized_target or redirect.destination_url,
                source_page_id=page.id,
                source_evidence_id=redirect_evidence_id,
                discovery_method="redirect",
                skip_reason=_failure_reason(error),
                redirect_status_code=redirect.status_code,
            )
        )


def _record_collection_failure(
    pages: list[CrawlPageRecord],
    frontier: list[CrawlFrontierRecord],
    target: _CrawlTarget,
    error: Exception,
    *,
    redirect_evidence_id: str | None = None,
) -> None:
    navigation_status = _navigation_status_for_error(error)
    classification = classify_capture(
        title=None,
        final_url=None,
        visible_text="",
        navigation_status=navigation_status,
        error_type="timeout" if navigation_status == "timed_out" else type(error).__name__,
    )
    blocked_requests = error.blocked_requests if isinstance(error, CollectionError) else []
    blocked_popup_count = error.blocked_popup_count if isinstance(error, CollectionError) else 0
    blocked_download_count = (
        error.blocked_download_count if isinstance(error, CollectionError) else 0
    )
    redirects = error.redirects if isinstance(error, CollectionError) else []
    reason = _failure_reason(error)
    public_status = derive_public_status(
        navigation_status=navigation_status,
        access_outcome=classification.access_outcome,
        capture_adequacy=CaptureAdequacy.FAILED,
    )
    _replace_page(
        pages,
        target.page_id,
        state="failed",
        navigation_status=navigation_status,
        capture_outcome=classification.outcome,
        content_usable=classification.content_usable,
        access_outcome=classification.access_outcome,
        capture_adequacy=CaptureAdequacy.FAILED,
        extraction_eligible=False,
        extraction_skip_reason="navigation_not_captured",
        public_status=public_status,
        limitation_reasons=[reason],
        classification_reasons=classification.reasons,
        redirects=redirects,
        redirect_evidence_id=redirect_evidence_id,
        blocked_requests=blocked_requests,
        blocked_popup_count=blocked_popup_count,
        blocked_download_count=blocked_download_count,
        skip_reason=reason,
        error=str(error),
    )
    _replace_frontier(frontier, target.frontier_id, state="failed", skip_reason=reason)


def _failure_reason(error: Exception) -> str:
    if isinstance(error, CollectionError):
        return error.reason_code
    return "timeout" if "timeout" in str(error).casefold() else "navigation_error"


def _write_case_outputs(
    *,
    storage: CaseStorage,
    case: CaseRecord,
    pages: list[CrawlPageRecord],
    frontier: list[CrawlFrontierRecord],
    evidence: list[EvidenceRecord],
    entities: list[ExtractedEntity],
    observations: list[SemanticObservation],
    candidate_generation: CandidateGeneration,
) -> None:
    storage.write_json("pages.json", [page.model_dump(mode="json") for page in pages])
    storage.write_json("frontier.json", [record.model_dump(mode="json") for record in frontier])
    storage.write_json("evidence.json", [record.model_dump(mode="json") for record in evidence])
    storage.write_json("entities.json", [entity.model_dump(mode="json") for entity in entities])
    storage.write_json(
        "observations.json", [observation.model_dump(mode="json") for observation in observations]
    )
    storage.write_json("candidates.json", candidate_generation.document.model_dump(mode="json"))
    storage.write_json(
        "candidate_observations.json",
        [observation.model_dump(mode="json") for observation in candidate_generation.observations],
    )
    if case.status == "completed":
        graph = build_graph(case=case, evidence=evidence, entities=entities, pages=pages)
        storage.write_json("graph.json", graph.model_dump(mode="json"))
    storage.write_json("case.json", case.model_dump(mode="json"))


def _attach_observation_crops(
    *,
    storage: CaseStorage,
    observations: list[SemanticObservation],
    screenshot: bytes,
    collected_at: datetime,
    evidence: list[EvidenceRecord],
) -> list[SemanticObservation]:
    """Create bounded crops for stable viewport boxes and retain observations on crop failure."""

    try:
        image = Image.open(BytesIO(screenshot)).convert("RGB")
    except OSError:
        return observations
    attached: list[SemanticObservation] = []
    for observation in observations:
        coordinates = observation.crop_coordinates
        if coordinates is None:
            attached.append(observation)
            continue
        left = max(0, int(coordinates["x"]) - 12)
        top = max(0, int(coordinates["y"]) - 12)
        right = min(image.width, int(coordinates["x"] + coordinates["width"]) + 12)
        bottom = min(image.height, int(coordinates["y"] + coordinates["height"]) + 12)
        if right <= left or bottom <= top or (right - left) * (bottom - top) > 2_000_000:
            attached.append(observation)
            continue
        crop = image.crop((left, top, right, bottom))
        output = BytesIO()
        crop.save(output, format="PNG")
        crop_evidence = storage.save_evidence_crop(
            output.getvalue(),
            observation_id=observation.id,
            source_url=observation.source_url,
            collected_at=collected_at,
            page_id=observation.source_page_id,
            image_dimensions={"width": crop.width, "height": crop.height},
        )
        evidence.append(crop_evidence)
        attached.append(
            observation.model_copy(
                update={
                    "crop_evidence_id": crop_evidence.id,
                    "crop_coordinates": {
                        "x": float(left),
                        "y": float(top),
                        "width": float(right - left),
                        "height": float(bottom - top),
                    },
                }
            )
        )
    return attached


def _navigation_status_for_error(error: Exception) -> str:
    if _failure_reason(error) == "timeout" or "timeout" in str(error).casefold():
        return "timed_out"
    if _failure_reason(error) in {
        "unsafe_destination",
        "external_host",
        "unsupported_content_type",
        "redirect_limit",
        "request_budget",
        "response_budget",
    }:
        return "blocked_by_policy"
    return "failed"


def _page_by_id(pages: list[CrawlPageRecord], page_id: str) -> CrawlPageRecord:
    for page in pages:
        if page.id == page_id:
            return page
    raise ValueError(f"Unknown crawl page id: {page_id}")


def _replace_page(pages: list[CrawlPageRecord], page_id: str, **update: object) -> CrawlPageRecord:
    for index, page in enumerate(pages):
        if page.id == page_id:
            replacement = page.model_copy(update=update)
            pages[index] = replacement
            return replacement
    raise ValueError(f"Unknown crawl page id: {page_id}")


def _replace_frontier(
    frontier: list[CrawlFrontierRecord], frontier_id: str, **update: object
) -> CrawlFrontierRecord:
    for index, record in enumerate(frontier):
        if record.id == frontier_id:
            replacement = record.model_copy(update=update)
            frontier[index] = replacement
            return replacement
    raise ValueError(f"Unknown frontier id: {frontier_id}")


def _next_page_id(pages: list[CrawlPageRecord]) -> str:
    return f"page-{len(pages) + 1:03d}"


def _next_frontier_id(frontier: list[CrawlFrontierRecord]) -> str:
    return f"frontier-{len(frontier) + 1:04d}"
