"""Import a real bounded capture into the append-only investigation runtime."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from hawkeye.agent import AgentVisibleContext, CodexInvestigator
from hawkeye.collector.safety import SafetyPolicy, UnsafeUrlError
from hawkeye.interaction import InteractionBudget
from hawkeye.interaction.models import InteractiveElement, StableElementReference
from hawkeye.interaction.policy import validate_read_only_interaction
from hawkeye.models import InvestigationResult, SemanticObservation

from .models import CandidateLead
from .reducer import reduce_events
from .store import InvestigationStore

_SAFE_REVEAL = re.compile(r"\b(promo(?:tion)?|about|information|menu|help|news|event)\b", re.I)
_CANDIDATE_TOKEN = re.compile(r"[a-z]+\d+|\d+[a-z]+|\d{3,}", re.I)
_NON_CANDIDATE_HOSTS = {
    "facebook.com",
    "google.com",
    "googleapis.com",
    "googletagmanager.com",
    "instagram.com",
    "livechatinc.com",
    "t.me",
    "telegram.me",
    "twitter.com",
    "wa.me",
    "whatsapp.com",
    "youtube.com",
}


def run_live_investigation(
    result: InvestigationResult,
    output_directory: Path | str,
    *,
    investigator: CodexInvestigator | None,
    known_cases: list[dict[str, object]],
    safety_policy: SafetyPolicy,
) -> dict[str, object]:
    """Create one event-sourced run from a verified public collection."""

    destination = Path(output_directory).expanduser().resolve()
    if destination.exists():
        raise FileExistsError(f"Investigation output already exists: {destination}")
    destination.mkdir(parents=True)
    artifacts = destination / "artifacts"
    artifacts.mkdir()
    run_id = f"run-{uuid.uuid4().hex}"
    case_id = result.case.case_id
    store = InvestigationStore(destination / "investigation.sqlite3")
    started = store.append_event(
        case_id=case_id,
        run_id=run_id,
        kind="run.started",
        payload={
            "seed_url": result.case.seed_url,
            "collection_mode": "real_world",
            "source_case_id": case_id,
        },
    )
    collection = store.append_event(
        case_id=case_id,
        run_id=run_id,
        kind="collection.started",
        payload={"page_budget": 3, "depth_budget": 1},
        causation_event_id=started.event_id,
    )
    page_events: dict[str, str] = {}
    for index, page in enumerate(result.pages):
        captured = store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind="artifact.captured",
            payload={
                "node_id": f"page:{page.id}",
                "root": index == 0,
                "page_id": page.id,
                "label": page.final_url or page.normalized_url,
                "url": page.final_url or page.normalized_url,
                "depth": page.depth,
                "parent_node_id": (f"page:{page.parent_page_id}" if page.parent_page_id else None),
                "capture_adequacy": page.capture_adequacy.value if page.capture_adequacy else None,
                "extraction_tier": page.extraction_tier,
                "public_status": page.public_status.value if page.public_status else None,
                "html_evidence_id": page.html_evidence_id,
                "screenshot_evidence_id": page.screenshot_evidence_id,
                "initial_screenshot_evidence_id": page.initial_screenshot_evidence_id,
                "full_page_screenshot_evidence_id": page.full_page_screenshot_evidence_id,
                "source_case_id": case_id,
            },
            causation_event_id=collection.event_id,
        )
        page_events[page.id] = captured.event_id

    known_by_host = _known_cases_by_host(known_cases)
    observation_event_ids: dict[str, str] = {}
    captured_urls = {
        _comparable_url(page.final_url or page.normalized_url) for page in result.pages
    }
    projected_observations = _meaningful_observations(
        result.observations,
        captured_urls=captured_urls,
    )
    projected_observations = _deduplicate_observations(
        [
            *projected_observations,
            *_frontier_observations(result, known_by_host),
        ]
    )
    for observation in projected_observations:
        matched = None
        if observation.observation_type in {
            "public_outgoing_link",
            "public_redirect_target",
        }:
            matched = known_by_host.get(_hostname(observation.normalized_value))
        event = store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind="observation.created",
            payload={
                "observation_id": observation.id,
                "node_id": _observation_node_id(observation),
                "source_node_id": f"page:{observation.source_page_id}",
                "observation_type": observation.observation_type,
                "normalized_value": observation.normalized_value,
                "raw_value": observation.raw_value,
                "source_artifact_id": observation.source_artifact_id,
                "screenshot_evidence_id": observation.screenshot_evidence_id,
                "confidence": observation.confidence,
                "evidence_strength": observation.evidence_strength,
                "limitations": observation.limitations,
                "provisional": bool(observation.attributes.get("provisional")),
                "matched_case_id": matched.get("case_id") if matched else None,
                "matched_capture_status": matched.get("public_status") if matched else None,
            },
            causation_event_id=page_events.get(observation.source_page_id, collection.event_id),
        )
        observation_event_ids[observation.id] = event.event_id
        if matched:
            store.append_event(
                case_id=case_id,
                run_id=run_id,
                kind="entity.matched",
                payload={
                    "observation_id": observation.id,
                    "target_case_id": matched.get("case_id"),
                    "target_url": matched.get("final_url_display"),
                    "match_method": "normalized_hostname",
                },
                causation_event_id=event.event_id,
            )

    primary_html = _primary_html(result)
    elements, references = _interactive_map(
        primary_html, result.case.final_url or result.case.seed_url
    )
    permitted: list[StableElementReference] = []
    blocked_preview = 0
    source_host = _hostname(result.case.final_url or result.case.seed_url)
    for element, reference in zip(elements, references, strict=True):
        allowed, reason, checks = validate_read_only_interaction(element)
        if allowed and element.destination_url:
            destination_host = _hostname(element.destination_url)
            if destination_host and destination_host != source_host:
                allowed = False
                reason = "external_navigation_requires_collection_approval"
                checks = {
                    **checks,
                    "same_site_navigation": False,
                    "block_reason": reason,
                }
        discovered = store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind="interactive_element.discovered",
            payload={
                "element_reference": reference.model_dump(mode="json"),
                "policy_allowed": allowed,
                "policy_reason": reason,
            },
            causation_event_id=collection.event_id,
        )
        if allowed:
            permitted.append(reference)
        elif blocked_preview < 12:
            requested = store.append_event(
                case_id=case_id,
                run_id=run_id,
                kind="tool.requested",
                payload={
                    "action": "policy_preflight",
                    "tool_name": "page_click_read_only",
                    "element_reference": reference.model_dump(mode="json"),
                    "executed": False,
                },
                causation_event_id=discovered.event_id,
            )
            store.append_event(
                case_id=case_id,
                run_id=run_id,
                kind="tool.blocked",
                payload={
                    "reason": reason,
                    "policy_checks": checks,
                    "policy_preflight": True,
                    "executed": False,
                },
                causation_event_id=requested.event_id,
            )
            blocked_preview += 1

    gap = store.append_event(
        case_id=case_id,
        run_id=run_id,
        kind="evidence_gap.created",
        payload={"gap": "Inspect one policy-permitted public information route."},
        causation_event_id=collection.event_id,
    )
    objective = store.append_event(
        case_id=case_id,
        run_id=run_id,
        kind="agent.objective.created",
        payload={"objective": "Choose at most one safe public information action."},
        causation_event_id=gap.event_id,
    )
    context = AgentVisibleContext(
        objective="Choose at most one safe public information action.",
        current_case_state={
            "case_id": case_id,
            "capture_adequacy": result.case.capture_adequacy.value
            if result.case.capture_adequacy
            else None,
            "extraction_tier": result.case.extraction_tier,
        },
        normalized_observations=[
            f"{item.observation_type}:{item.normalized_value}" for item in projected_observations
        ][:100],
        safe_interactive_elements=permitted[:40],
        policy_budget=InteractionBudget(max_interactions=1),
        evidence_gap="Inspect one policy-permitted public information route.",
    )
    step = (investigator or CodexInvestigator(None)).choose(context)
    if step.mode == "deterministic_fallback":
        store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind="agent.fallback.activated",
            payload={"failures": [item.model_dump(mode="json") for item in step.failures]},
            causation_event_id=objective.event_id,
        )
    action_summary: dict[str, object] | None = None
    if step.decision.action == "tool_request" and step.decision.element_reference is not None:
        chosen_reference = step.decision.element_reference
        chosen_element = next(
            (item for item in elements if item.element_id == chosen_reference.element_id), None
        )
        requested = store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind="tool.requested",
            payload={**step.decision.model_dump(mode="json"), "executed": True},
            causation_event_id=objective.event_id,
        )
        if chosen_element is None:
            action_summary = {"status": "stale_reference", "reason": "element_not_found"}
        else:
            action_summary = _execute_live_interaction(
                result.case.final_url or result.case.seed_url,
                chosen_element,
                chosen_reference,
                safety_policy=safety_policy,
                artifacts=artifacts,
            )
        completed = store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind="tool.completed"
            if action_summary.get("status") == "completed"
            else "tool.blocked",
            payload=action_summary,
            causation_event_id=requested.event_id,
        )
        if action_summary.get("status") == "completed":
            route_url = str(action_summary.get("url"))
            store.append_event(
                case_id=case_id,
                run_id=run_id,
                kind="artifact.captured",
                payload={
                    "node_id": f"route:{hashlib.sha256(route_url.encode()).hexdigest()[:12]}",
                    "label": route_url,
                    "url": route_url,
                    "depth": 1,
                    "capture_adequacy": "adequate",
                    "extraction_tier": "verified",
                    "interaction_artifact": action_summary.get("state_artifact"),
                    "screenshot_artifact": action_summary.get("screenshot_artifact"),
                    "source_case_id": case_id,
                },
                causation_event_id=completed.event_id,
            )

    leads = _candidate_observations(
        projected_observations,
        source_url=result.case.final_url or result.case.seed_url,
        known_by_host=known_by_host,
    )
    pending_leads: list[dict[str, object]] = []
    for index, observation in enumerate(leads[:5], start=1):
        lead = CandidateLead(
            lead_id=f"lead-live-{index:02d}-{uuid.uuid4().hex[:8]}",
            case_id=case_id,
            run_id=run_id,
            url=observation.normalized_value,
            discovery_method="direct_link",
            source_observation_ids=[observation.id],
            collection_mode="real_world",
            initial_status="waiting_for_approval",
            created_at=datetime.now(UTC),
        )
        search = store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind="search.started",
            payload={
                "strategy": "direct_public_link",
                "source_observation_id": observation.id,
            },
            causation_event_id=observation_event_ids.get(observation.id, objective.event_id),
        )
        store.add_lead(lead, causation_event_id=search.event_id)
        selected = store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind="candidate_page.selected",
            payload={"lead_id": lead.lead_id, "url": lead.url},
            causation_event_id=search.event_id,
        )
        store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind="candidate_page.approval_required",
            payload={
                "lead_id": lead.lead_id,
                "url": lead.url,
                "source_observation_id": observation.id,
                "source_artifact_id": observation.source_artifact_id,
            },
            causation_event_id=selected.event_id,
        )
        pending_leads.append(lead.model_dump(mode="json"))

    if not pending_leads:
        store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind="run.completed",
            payload={"lead_status": "no_uncollected_candidate"},
            causation_event_id=objective.event_id,
        )
    graph = reduce_events(store.events(run_id))
    summary: dict[str, object] = {
        "case_id": case_id,
        "run_id": run_id,
        "source_kind": "live_capture",
        "source_case_id": case_id,
        "seed_url": result.case.seed_url,
        "agent_mode": step.mode,
        "agent_model": getattr(getattr(investigator, "client", None), "model", None),
        "lead_status": "waiting_for_approval" if pending_leads else "complete",
        "pending_leads": pending_leads,
        "assertion_id": None,
        "action_summary": action_summary,
        "capture_adequacy": result.case.capture_adequacy.value
        if result.case.capture_adequacy
        else None,
        "extraction_tier": result.case.extraction_tier,
        "graph": graph.model_dump(mode="json"),
    }
    (destination / "run-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def _primary_html(result: InvestigationResult) -> str:
    if not result.pages or result.pages[0].html_evidence_id is None:
        return ""
    path = Path(result.case_directory) / "pages" / f"{result.pages[0].id}.html"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _interactive_map(
    html: str, source_url: str
) -> tuple[list[InteractiveElement], list[StableElementReference]]:
    soup = BeautifulSoup(html, "html.parser")
    snapshot = f"snapshot-{hashlib.sha256(html.encode()).hexdigest()[:12]}"
    elements: list[InteractiveElement] = []
    references: list[StableElementReference] = []
    seen: set[tuple[str, str | None]] = set()
    for tag in soup.select("a, button, [role='button']")[:300]:
        if not isinstance(tag, Tag):
            continue
        text = re.sub(r"\s+", " ", tag.get_text(" ", strip=True))[:200]
        aria = str(tag.get("aria-label", "")).strip()
        label = aria or text
        if not label:
            continue
        raw_href = str(tag.get("href", "")).strip() if tag.name == "a" else ""
        href = urljoin(source_url, raw_href) if raw_href and raw_href != "#" else None
        key = (label.casefold(), href)
        if key in seen:
            continue
        seen.add(key)
        selector = _selector_for(tag)
        behavior = (
            "open_public_link" if href else "reveal_tab" if _SAFE_REVEAL.search(label) else "none"
        )
        form = tag.find_parent("form")
        element_id = f"live-{len(elements) + 1:03d}"
        element = InteractiveElement(
            element_id=element_id,
            dom_path=selector,
            role="link" if tag.name == "a" else str(tag.get("role") or "button"),
            tag=tag.name or "button",
            accessible_name=label,
            visible_text=text,
            href=href,
            action=str(tag.get("formaction", "")) or None,
            form_owner=str(form.get("id", "form")) if isinstance(form, Tag) else None,
            form_action=(
                urljoin(source_url, str(form.get("action", "")))
                if isinstance(form, Tag) and form.get("action")
                else None
            ),
            download_attribute=tag.has_attr("download"),
            opens_new_tab=str(tag.get("target", "")).casefold() == "_blank",
            declared_behavior=behavior,  # type: ignore[arg-type]
            destination_url=href,
        )
        payload = {
            "dom_path": selector,
            "role": element.role,
            "tag": element.tag,
            "accessible_name": label,
            "visible_text": text,
            "href": href,
            "action": element.action,
            "snapshot": snapshot,
        }
        fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        reference = StableElementReference(
            reference_id=f"ref-{element_id}-{snapshot}",
            discovery_snapshot_id=snapshot,
            element_id=element_id,
            dom_path=selector,
            role=element.role,
            tag=element.tag,
            accessible_name=label,
            visible_text=text,
            href=href,
            action=element.action,
            element_fingerprint=fingerprint,
        )
        elements.append(element)
        references.append(reference)
    return elements, references


def _execute_live_interaction(
    source_url: str,
    element: InteractiveElement,
    reference: StableElementReference,
    *,
    safety_policy: SafetyPolicy,
    artifacts: Path,
) -> dict[str, object]:
    permitted, reason, checks = validate_read_only_interaction(element)
    if not permitted:
        return {
            "status": "blocked",
            "reason": reason,
            "policy_checks": checks,
            "executed": False,
        }
    safety_policy.validate_crawl_url(source_url, refresh_dns=True)
    source_host = _hostname(source_url)
    request_count = 0
    blocked_requests: list[str] = []
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                accept_downloads=False, viewport={"width": 1440, "height": 1024}
            )
            page = context.new_page()

            def route_request(route: object) -> None:
                nonlocal request_count
                request_count += 1
                request = route.request  # type: ignore[attr-defined]
                try:
                    if request_count > 200:
                        raise UnsafeUrlError("interaction request budget exceeded")
                    safety_policy.validate_url(request.url, refresh_dns=True)
                    if request.is_navigation_request() and request.resource_type == "document":
                        target = safety_policy.validate_crawl_url(request.url, refresh_dns=True)
                        if target.hostname.removeprefix("www.") != source_host:
                            raise UnsafeUrlError("interaction navigation left the approved host")
                except UnsafeUrlError as error:
                    blocked_requests.append(str(error)[:300])
                    route.abort()  # type: ignore[attr-defined]
                    return
                route.continue_()  # type: ignore[attr-defined]

            context.route("**/*", route_request)
            page.on("popup", lambda popup: popup.close())
            page.on("download", lambda download: download.cancel())
            page.goto(source_url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(5_000)
            locator = page.locator(reference.dom_path)
            if locator.count() != 1:
                browser.close()
                return {
                    "status": "stale_reference",
                    "reason": "selector_not_unique",
                    "executed": False,
                }
            observed_label = re.sub(r"\s+", " ", locator.inner_text(timeout=2_000)).strip()[:200]
            if reference.visible_text and observed_label != reference.visible_text:
                browser.close()
                return {
                    "status": "stale_reference",
                    "reason": "visible_text_changed",
                    "executed": False,
                }
            locator.click(timeout=5_000)
            page.wait_for_timeout(3_000)
            final_url = page.url
            screenshot = page.screenshot(full_page=False, timeout=5_000)
            html = page.content()
            visible_text = page.locator("body").inner_text(timeout=5_000)
            screenshot_name = "interaction-001.png"
            state_name = "interaction-001.json"
            (artifacts / screenshot_name).write_bytes(screenshot)
            state = {
                "url": final_url,
                "title": page.title(),
                "visible_text_chars": len(visible_text),
                "html_sha256": hashlib.sha256(html.encode()).hexdigest(),
                "screenshot_sha256": hashlib.sha256(screenshot).hexdigest(),
                "request_count": request_count,
                "blocked_request_count": len(blocked_requests),
                "selected_element": reference.model_dump(mode="json"),
            }
            (artifacts / state_name).write_text(
                json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            browser.close()
    except Exception as error:  # browser errors become bounded, auditable tool failures
        return {
            "status": "blocked",
            "reason": f"interaction_execution_failed:{type(error).__name__}",
            "executed": False,
        }
    return {
        "status": "completed",
        "reason": reason,
        "url": final_url,
        "state_artifact": state_name,
        "screenshot_artifact": screenshot_name,
        "request_count": request_count,
        "blocked_request_count": len(blocked_requests),
        "executed": True,
    }


def _selector_for(tag: Tag) -> str:
    identifier = str(tag.get("id", ""))
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,80}", identifier):
        return f"{tag.name}#{identifier}"
    parts: list[str] = []
    current: Tag | None = tag
    while current is not None and current.name not in {"[document]", "html"} and len(parts) < 8:
        part = current.name
        parent = current.parent if isinstance(current.parent, Tag) else None
        if parent is not None:
            siblings = list(parent.find_all(current.name, recursive=False))
            if len(siblings) > 1:
                part += f":nth-of-type({siblings.index(current) + 1})"
        parts.insert(0, part)
        current = parent
    return " > ".join(parts)


def _meaningful_observations(
    items: list[SemanticObservation], *, captured_urls: set[str]
) -> list[SemanticObservation]:
    limits = {
        "claimed_brand_identity": 3,
        "public_outgoing_link": 18,
        "public_redirect_target": 6,
        "public_telegram_alias": 10,
        "public_whatsapp_link": 10,
        "public_phone_number": 10,
        "public_email_address": 10,
        "public_payment_provider": 12,
        "public_payment_method": 6,
        "public_offer_claim": 6,
        "public_referral_code": 10,
        "public_tracking_identifier": 10,
        "public_download_destination": 10,
        "public_legal_or_license_claim": 6,
    }
    counts: dict[str, int] = {}
    result: list[SemanticObservation] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        if item.observation_type in {"public_outgoing_link", "public_redirect_target"}:
            if _comparable_url(item.normalized_value) in captured_urls:
                continue
            if _is_non_candidate_host(_hostname(item.normalized_value)):
                continue
        key = (item.observation_type, item.normalized_value)
        if key in seen or counts.get(item.observation_type, 0) >= limits.get(
            item.observation_type, 0
        ):
            continue
        seen.add(key)
        counts[item.observation_type] = counts.get(item.observation_type, 0) + 1
        result.append(item)
    return result


def _candidate_observations(
    observations: list[SemanticObservation],
    *,
    source_url: str,
    known_by_host: dict[str, dict[str, object]],
) -> list[SemanticObservation]:
    source_host = _hostname(source_url)
    token_match = _CANDIDATE_TOKEN.search(source_host)
    token = token_match.group(0).casefold() if token_match else ""
    candidates: list[SemanticObservation] = []
    seen: set[str] = set()
    for item in observations:
        if item.observation_type != "public_outgoing_link":
            continue
        target_host = _hostname(item.normalized_value)
        if not target_host or target_host == source_host or target_host in seen:
            continue
        seen.add(target_host)
        if _is_non_candidate_host(target_host) or target_host in known_by_host:
            continue
        if token and token in target_host:
            candidates.append(item)
    return sorted(candidates, key=lambda item: item.normalized_value)


def _frontier_observations(
    result: InvestigationResult,
    known_by_host: dict[str, dict[str, object]],
) -> list[SemanticObservation]:
    """Promote evidence-backed direct anchors needed for cross-case graph matching."""

    source_host = _hostname(result.case.final_url or result.case.seed_url)
    token_match = _CANDIDATE_TOKEN.search(source_host)
    token = token_match.group(0).casefold() if token_match else ""
    pages = {item.id: item for item in result.pages}
    observations: list[SemanticObservation] = []
    for item in result.frontier:
        if (
            item.discovery_method != "html_anchor"
            or not item.normalized_url
            or not item.source_page_id
            or not item.source_evidence_id
        ):
            continue
        target_host = _hostname(item.normalized_url)
        if (
            not target_host
            or target_host == source_host
            or _is_non_candidate_host(target_host)
            or (target_host not in known_by_host and (not token or token not in target_host))
        ):
            continue
        page = pages.get(item.source_page_id)
        if page is None or page.screenshot_evidence_id is None:
            continue
        limitations = []
        if page.extraction_tier != "verified":
            limitations.append("direct_anchor_from_provisional_or_withheld_semantic_capture")
        observations.append(
            SemanticObservation(
                id=f"frontier-observation-{item.id}",
                observation_type="public_outgoing_link",
                raw_value=item.original_href or item.normalized_url,
                normalized_value=item.normalized_url,
                source_page_id=item.source_page_id,
                source_url=page.final_url or page.normalized_url,
                source_artifact_id=item.source_evidence_id,
                surrounding_text=item.anchor_text or "",
                screenshot_evidence_id=page.screenshot_evidence_id,
                confidence=0.9 if page.extraction_tier == "verified" else 0.75,
                extraction_method="persisted_crawl_frontier_anchor",
                evidence_strength="strong" if page.extraction_tier == "verified" else "moderate",
                limitations=limitations,
                attributes={"frontier_state": item.state, "skip_reason": item.skip_reason},
            )
        )
    return observations


def _deduplicate_observations(
    observations: list[SemanticObservation],
) -> list[SemanticObservation]:
    result: list[SemanticObservation] = []
    seen: set[tuple[str, str]] = set()
    for item in observations:
        key = (item.observation_type, item.normalized_value)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _known_cases_by_host(items: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for item in items:
        host = _hostname(str(item.get("final_url_display") or ""))
        if host:
            result[host] = item
    return result


def _observation_node_id(item: SemanticObservation) -> str:
    material = f"{item.observation_type}|{item.normalized_value}".encode()
    return f"observable:{hashlib.sha256(material).hexdigest()[:16]}"


def _hostname(value: str) -> str:
    try:
        return (urlsplit(value).hostname or "").casefold().removeprefix("www.")
    except ValueError:
        return ""


def _comparable_url(value: str) -> str:
    return value.rstrip("/").casefold()


def _is_non_candidate_host(host: str) -> bool:
    return any(host == item or host.endswith(f".{item}") for item in _NON_CANDIDATE_HOSTS)
