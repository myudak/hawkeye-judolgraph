"""Import a real bounded capture into the append-only investigation runtime."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from hawkeye.agent import AgentVisibleContext, ModelInvestigator
from hawkeye.browser import launch_chromium
from hawkeye.collector.safety import SafetyPolicy, UnsafeUrlError
from hawkeye.interaction import InteractionBudget
from hawkeye.interaction.models import (
    InteractionDecision,
    InteractiveElement,
    StableElementReference,
)
from hawkeye.interaction.policy import validate_read_only_interaction
from hawkeye.models import InvestigationResult, SemanticObservation
from hawkeye.semantic_evidence import extract_semantic_observations

from .models import CandidateAssertion, CandidateLead
from .reducer import reduce_events
from .store import InvestigationStore

_SAFE_REVEAL = re.compile(
    r"\b(contact(?: us)?|hubungi(?: kami)?|kontak|support|promo(?:tion)?|about|"
    r"information|menu|help|news|event)\b",
    re.I,
)
_CONTACT_REVEAL = re.compile(
    r"\b(contact(?: us)?|hubungi(?: kami)?|kontak|support|help)\b",
    re.I,
)
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

_CONTACT_OBSERVATION_TYPES = {
    "public_telegram_alias",
    "public_telegram_contact",
    "public_whatsapp_link",
    "public_phone_number",
    "public_email_address",
}

LiveProgressCallback = Callable[[str, dict[str, object]], None]

_ELEMENT_RESOLUTION_JS = r"""
elements => elements.slice(0, 400).map((element, index) => {
  const style = window.getComputedStyle(element);
  const rect = element.getBoundingClientRect();
  const text = (element.innerText || element.textContent || "").replace(/\s+/g, " ").trim();
  return {
    index,
    tag: element.tagName.toLowerCase(),
    text: text.slice(0, 200),
    aria: (element.getAttribute("aria-label") || "").trim().slice(0, 200),
    href: element instanceof HTMLAnchorElement && element.href ? element.href : null,
    action: element.getAttribute("formaction"),
    visible:
      style.display !== "none" &&
      style.visibility !== "hidden" &&
      Number(style.opacity || "1") > 0 &&
      rect.width > 0 &&
      rect.height > 0,
  };
})
"""


@dataclass(frozen=True)
class _LiveExpansionResult:
    action_summaries: list[dict[str, object]]
    observations: list[SemanticObservation]
    agent_mode: str
    stop_reason: str
    stopped_event_id: str


@dataclass(frozen=True)
class _ResolvedLiveReference:
    locator: Any
    strategy: str
    diagnostics: dict[str, object]


def run_live_investigation(
    result: InvestigationResult,
    output_directory: Path | str,
    *,
    investigator: ModelInvestigator | None,
    known_cases: list[dict[str, object]],
    safety_policy: SafetyPolicy,
    investigation_name: str = "",
    guided: bool = True,
    progress_callback: LiveProgressCallback | None = None,
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
            "investigation_name": investigation_name,
            "investigation_mode": "guided" if guided else "capture_only",
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

    contact_references = [
        reference
        for reference in permitted
        if _CONTACT_REVEAL.search(reference.accessible_name or "")
    ]
    gap = store.append_event(
        case_id=case_id,
        run_id=run_id,
        kind="evidence_gap.created",
        payload={
            "gap": (
                "Prefer a same-site Contact, Hubungi Kami, or support information route that may "
                "reveal public phone, WhatsApp, Telegram, or email evidence."
            )
        },
        causation_event_id=collection.event_id,
    )
    objective = store.append_event(
        case_id=case_id,
        run_id=run_id,
        kind="agent.objective.created",
        payload={
            "objective_id": (
                "find_public_contact" if contact_references else "find_related_public_destination"
            ),
            "objective": (
                "Find a public contact channel and one defensible related destination using at "
                "most five policy-validated steps."
            ),
            "max_iterations": 5,
            "max_interactions": 3,
        },
        causation_event_id=gap.event_id,
    )
    if guided:
        expansion = _run_live_agent_loop(
            result=result,
            projected_observations=projected_observations,
            initial_elements=elements,
            initial_references=(contact_references or permitted),
            investigator=investigator or ModelInvestigator(None),
            store=store,
            run_id=run_id,
            case_id=case_id,
            objective_event_id=objective.event_id,
            safety_policy=safety_policy,
            artifacts=artifacts,
            observation_event_ids=observation_event_ids,
            workspace_id=destination.name,
            progress_callback=progress_callback,
        )
    else:
        stopped = store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind="agent.stopped",
            payload={
                "objective_id": objective.payload["objective_id"],
                "stop_reason": "capture_only_mode",
                "iterations": 0,
                "interactions": 0,
            },
            causation_event_id=objective.event_id,
        )
        expansion = _LiveExpansionResult(
            action_summaries=[],
            observations=[],
            agent_mode="not_requested",
            stop_reason="capture_only_mode",
            stopped_event_id=stopped.event_id,
        )
    action_summaries = expansion.action_summaries
    interaction_observations = expansion.observations
    projected_observations = _deduplicate_observations(
        [*projected_observations, *interaction_observations]
    )
    action_summary = action_summaries[-1] if action_summaries else None
    agent_mode = expansion.agent_mode
    agent_stop_reason = expansion.stop_reason

    temporal_comparison = _persist_temporal_comparison(
        store=store,
        case_id=case_id,
        run_id=run_id,
        source_url=result.case.final_url or result.case.seed_url,
        observations=projected_observations,
        known_cases=known_cases,
        causation_event_id=expansion.stopped_event_id,
    )
    relationship_assertion_ids = _persist_exact_cross_case_matches(
        store=store,
        case_id=case_id,
        run_id=run_id,
        source_url=result.case.final_url or result.case.seed_url,
        observations=projected_observations,
        known_cases=known_cases,
        causation_event_id=expansion.stopped_event_id,
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
            payload={
                "lead_status": "no_uncollected_candidate",
                "assertion_ids": relationship_assertion_ids,
            },
            causation_event_id=expansion.stopped_event_id,
        )
    graph = reduce_events(store.events(run_id))
    summary: dict[str, object] = {
        "case_id": case_id,
        "run_id": run_id,
        "source_kind": "live_capture",
        "source_case_id": case_id,
        "seed_url": result.case.seed_url,
        "investigation_name": investigation_name,
        "investigation_mode": "guided" if guided else "capture_only",
        "agent_mode": agent_mode,
        "agent_model": getattr(getattr(investigator, "client", None), "model", None),
        "agent_stop_reason": agent_stop_reason,
        "agent_steps": len(action_summaries),
        "lead_status": "waiting_for_approval" if pending_leads else "complete",
        "pending_leads": pending_leads,
        "assertion_id": relationship_assertion_ids[0] if relationship_assertion_ids else None,
        "assertion_ids": relationship_assertion_ids,
        "action_summary": action_summary,
        "action_summaries": action_summaries,
        "temporal_comparison": temporal_comparison,
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


def _run_live_agent_loop(
    *,
    result: InvestigationResult,
    projected_observations: list[SemanticObservation],
    initial_elements: list[InteractiveElement],
    initial_references: list[StableElementReference],
    investigator: ModelInvestigator,
    store: InvestigationStore,
    run_id: str,
    case_id: str,
    objective_event_id: str,
    safety_policy: SafetyPolicy,
    artifacts: Path,
    observation_event_ids: dict[str, str],
    workspace_id: str,
    progress_callback: LiveProgressCallback | None,
) -> _LiveExpansionResult:
    """Execute a feedback-driven, at-most-three-action live expansion."""

    budget = InteractionBudget(max_iterations=5, max_interactions=3)
    current_url = result.case.final_url or result.case.seed_url
    current_parent_node = f"page:{result.pages[0].id}"
    current_elements = {item.element_id: item for item in initial_elements}
    current_references = list(initial_references)
    observations = list(projected_observations)
    seen_observations = {
        (item.observation_type, item.normalized_value) for item in projected_observations
    }
    prior_results: list[InteractionDecision] = []
    attempted_signatures: set[tuple[str, str | None]] = set()
    attempted_reference_ids: list[str] = []
    action_summaries: list[dict[str, object]] = []
    modes: list[str] = []
    last_event_id = objective_event_id
    stop_reason = "max_iterations"
    stale_count = 0
    noop_count = 0

    for iteration in range(1, budget.max_iterations + 1):
        if any(item.observation_type in _CONTACT_OBSERVATION_TYPES for item in observations):
            stop_reason = "objective_satisfied"
            break
        if len(action_summaries) >= budget.max_interactions:
            stop_reason = "budget_exhausted"
            break
        eligible_references = [
            item
            for item in current_references
            if (item.accessible_name.casefold(), item.href) not in attempted_signatures
        ]
        context = AgentVisibleContext(
            objective=(
                "Find a public contact channel and one defensible related destination. Use a "
                "menu or public-information route when necessary, then stop."
            ),
            objective_id="find_public_contact",
            iteration=iteration,
            current_case_state={
                "case_id": case_id,
                "url": current_url,
                "capture_adequacy": (
                    result.case.capture_adequacy.value if result.case.capture_adequacy else None
                ),
                "extraction_tier": result.case.extraction_tier,
                "interaction_count": len(action_summaries),
                "objective_satisfied": False,
            },
            normalized_observations=[
                f"{item.observation_type}:{item.normalized_value}" for item in observations
            ][:200],
            safe_interactive_elements=eligible_references[:60],
            policy_budget=budget,
            prior_tool_results=prior_results[-5:],
            evidence_gap=(
                "A public phone, WhatsApp, Telegram, or email observation has not yet been "
                "preserved. Prefer Contact, Hubungi Kami, support, menu, or help routes."
            ),
            attempted_reference_ids=attempted_reference_ids[-20:],
            latest_state_delta=(prior_results[-1].model_dump(mode="json") if prior_results else {}),
        )
        step = investigator.choose(context)
        modes.append(step.mode)
        if step.mode == "deterministic_fallback":
            fallback = store.append_event(
                case_id=case_id,
                run_id=run_id,
                kind="agent.fallback.activated",
                payload={
                    "iteration": iteration,
                    "failures": [item.model_dump(mode="json") for item in step.failures],
                },
                causation_event_id=last_event_id,
            )
            last_event_id = fallback.event_id
        decision = step.decision
        if decision.action == "stop":
            stop_reason = decision.stop_reason or "agent_stop"
            break
        if decision.action != "tool_request" or decision.element_reference is None:
            stop_reason = "insufficient_evidence"
            break
        reference = decision.element_reference
        attempted_reference_ids.append(reference.reference_id)
        attempted_signatures.add((reference.accessible_name.casefold(), reference.href))
        element = current_elements.get(reference.element_id)
        requested = store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind="tool.requested",
            payload={
                **decision.model_dump(mode="json"),
                "iteration": iteration,
                "executed": element is not None,
            },
            causation_event_id=last_event_id,
        )
        if element is None:
            action_summary: dict[str, object] = {
                "status": "stale_reference",
                "reason": "element_not_found",
                "executed": False,
                "iteration": iteration,
            }
        else:
            action_summary = _execute_live_interaction(
                current_url,
                element,
                reference,
                safety_policy=safety_policy,
                artifacts=artifacts,
                interaction_index=iteration,
                workspace_id=workspace_id,
                tool_name=decision.tool_name or "page_click_read_only",
                progress_callback=progress_callback,
            )
            action_summary["iteration"] = iteration
        interaction_html = str(action_summary.pop("_html", ""))
        completed = store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind=(
                "tool.completed" if action_summary.get("status") == "completed" else "tool.blocked"
            ),
            payload=action_summary,
            causation_event_id=requested.event_id,
        )
        last_event_id = completed.event_id
        status = str(action_summary.get("status", "blocked"))
        if status == "completed":
            action_viewport = action_summary.get("viewport")
            _emit_live_progress(
                progress_callback,
                "interaction_preview_ready",
                workspace_id=workspace_id,
                artifact_name=action_summary.get("screenshot_artifact"),
                label=reference.accessible_name,
                tool_name=decision.tool_name or "page_click_read_only",
                iteration=iteration,
                url=action_summary.get("url"),
                viewport_width=action_viewport.get("width")
                if isinstance(action_viewport, dict)
                else None,
                viewport_height=action_viewport.get("height")
                if isinstance(action_viewport, dict)
                else None,
                target_bbox=action_summary.get("target_bbox"),
                sha256=action_summary.get("screenshot_sha256"),
            )
        else:
            _emit_live_progress(
                progress_callback,
                "agent_focus_blocked",
                workspace_id=workspace_id,
                iteration=iteration,
                label=reference.accessible_name,
                tool_name=decision.tool_name or "page_click_read_only",
                reason=action_summary.get("reason"),
            )
        if status != "completed":
            stale_count = stale_count + 1 if status == "stale_reference" else 0
            prior_results.append(
                InteractionDecision(
                    status=("stale_reference" if status == "stale_reference" else "blocked"),
                    tool_name=decision.tool_name or "page_click_read_only",
                    reason=str(action_summary.get("reason", "interaction_failed")),
                    snapshot_id=reference.discovery_snapshot_id,
                    before_snapshot_id=reference.discovery_snapshot_id,
                    state_changed=False,
                )
            )
            action_summaries.append(action_summary)
            if stale_count >= 2:
                stop_reason = "repeated_stale_reference"
                break
            continue

        stale_count = 0
        route_url = str(action_summary.get("url", current_url))
        route_node_id = f"route:{hashlib.sha256(route_url.encode()).hexdigest()[:12]}"
        route_event = store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind="artifact.captured",
            payload={
                "node_id": route_node_id,
                "label": route_url,
                "url": route_url,
                "depth": 1,
                "parent_node_id": current_parent_node,
                "parent_relation": "opened_safe_public_route",
                "capture_adequacy": "not_assessed_for_interaction",
                "extraction_tier": "provisional",
                "interaction_artifact": action_summary.get("state_artifact"),
                "screenshot_artifact": action_summary.get("screenshot_artifact"),
                "html_artifact": action_summary.get("html_artifact"),
                "visible_text_artifact": action_summary.get("visible_text_artifact"),
                "source_case_id": case_id,
                "iteration": iteration,
            },
            causation_event_id=completed.event_id,
        )
        extracted = (
            _meaningful_observations(
                extract_semantic_observations(
                    interaction_html,
                    source_page_id=route_node_id,
                    source_url=route_url,
                    source_artifact_id=str(action_summary.get("html_artifact")),
                    screenshot_evidence_id=str(action_summary.get("screenshot_artifact")),
                    observation_id_start=10_000 + iteration * 1_000,
                ),
                captured_urls={_comparable_url(route_url)},
            )
            if interaction_html
            else []
        )
        added: list[str] = []
        for observation in extracted:
            key = (observation.observation_type, observation.normalized_value)
            if key in seen_observations:
                continue
            seen_observations.add(key)
            observations.append(observation)
            added.append(f"{observation.observation_type}:{observation.normalized_value}")
            event = store.append_event(
                case_id=case_id,
                run_id=run_id,
                kind="observation.created",
                payload={
                    "observation_id": observation.id,
                    "node_id": _observation_node_id(observation),
                    "source_node_id": route_node_id,
                    "observation_type": observation.observation_type,
                    "normalized_value": observation.normalized_value,
                    "raw_value": observation.raw_value,
                    "source_artifact_id": observation.source_artifact_id,
                    "screenshot_evidence_id": observation.screenshot_evidence_id,
                    "surrounding_text": observation.surrounding_text,
                    "confidence": observation.confidence,
                    "evidence_strength": observation.evidence_strength,
                    "limitations": [
                        *observation.limitations,
                        "interaction_route_uses_bounded_post_click_observation",
                    ],
                    "provisional": True,
                    "iteration": iteration,
                },
                causation_event_id=route_event.event_id,
            )
            observation_event_ids[observation.id] = event.event_id

        next_elements, next_references = _interactive_map(interaction_html, route_url)
        next_permitted: list[StableElementReference] = []
        next_host = _hostname(route_url)
        for candidate_element, candidate_reference in zip(
            next_elements, next_references, strict=True
        ):
            allowed, reason, _ = validate_read_only_interaction(candidate_element)
            destination_host = _hostname(candidate_element.destination_url or "")
            if allowed and destination_host and destination_host != next_host:
                allowed = False
                reason = "external_navigation_requires_collection_approval"
            store.append_event(
                case_id=case_id,
                run_id=run_id,
                kind="interactive_element.discovered",
                payload={
                    "element_reference": candidate_reference.model_dump(mode="json"),
                    "policy_allowed": allowed,
                    "policy_reason": reason,
                    "iteration": iteration + 1,
                },
                causation_event_id=route_event.event_id,
            )
            if allowed:
                next_permitted.append(candidate_reference)
        state_changed = bool(added or next_permitted or route_url != current_url)
        action_summary.update(
            {
                "added_observations": added,
                "state_changed": state_changed,
                "next_safe_element_count": len(next_permitted),
            }
        )
        _emit_live_progress(
            progress_callback,
            "agent_observations_ready",
            workspace_id=workspace_id,
            iteration=iteration,
            label=reference.accessible_name,
            tool_name=decision.tool_name or "page_click_read_only",
            added_observation_count=len(added),
        )
        step_observed = store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind="agent.step.observed",
            payload={
                "iteration": iteration,
                "before_url": current_url,
                "after_url": route_url,
                "added_observations": added,
                "state_changed": state_changed,
                "next_safe_element_count": len(next_permitted),
            },
            causation_event_id=route_event.event_id,
        )
        last_event_id = step_observed.event_id
        prior_results.append(
            InteractionDecision(
                status="completed",
                tool_name=decision.tool_name or "page_click_read_only",
                reason=str(action_summary.get("reason", "validated_public_reveal")),
                snapshot_id=(
                    next_references[0].discovery_snapshot_id
                    if next_references
                    else reference.discovery_snapshot_id
                ),
                before_snapshot_id=reference.discovery_snapshot_id,
                observations=[item.normalized_value for item in observations],
                destination_url=route_url,
                added_observations=added,
                state_changed=state_changed,
            )
        )
        action_summaries.append(action_summary)
        noop_count = 0 if state_changed else noop_count + 1
        if noop_count >= 2:
            stop_reason = "repeated_noop"
            break
        current_url = route_url
        current_parent_node = route_node_id
        current_elements = {item.element_id: item for item in next_elements}
        current_references = next_permitted

    objective_satisfied = any(
        item.observation_type in _CONTACT_OBSERVATION_TYPES for item in observations
    )
    if objective_satisfied:
        stop_reason = "objective_satisfied"
    stopped = store.append_event(
        case_id=case_id,
        run_id=run_id,
        kind="agent.stopped",
        payload={
            "objective_id": "find_public_contact",
            "objective_satisfied": objective_satisfied,
            "stop_reason": stop_reason,
            "iterations": len(action_summaries),
            "final_url": current_url,
        },
        causation_event_id=last_event_id,
    )
    agent_mode = (
        "not_required"
        if not modes
        else "model"
        if all(item == "model" for item in modes)
        else "deterministic_fallback"
    )
    return _LiveExpansionResult(
        action_summaries=action_summaries,
        observations=[item for item in observations if item not in projected_observations],
        agent_mode=agent_mode,
        stop_reason=stop_reason,
        stopped_event_id=stopped.event_id,
    )


def _persist_exact_cross_case_matches(
    *,
    store: InvestigationStore,
    case_id: str,
    run_id: str,
    source_url: str,
    observations: list[SemanticObservation],
    known_cases: list[dict[str, object]],
    causation_event_id: str,
) -> list[str]:
    """Propose conservative relationships from exact normalized public observables."""

    relation_by_type = {
        "public_telegram_alias": "shares_public_contact_with",
        "public_telegram_contact": "shares_public_contact_with",
        "public_whatsapp_link": "shares_public_contact_with",
        "public_phone_number": "shares_public_contact_with",
        "public_email_address": "shares_public_contact_with",
        "public_redirect_target": "shares_redirect_target_with",
        "public_download_destination": "shares_download_destination_with",
        "public_referral_code": "shares_referral_code_with",
        "public_tracking_identifier": "candidate_related_to",
    }
    current_by_key: dict[tuple[str, str], SemanticObservation] = {
        (item.observation_type, item.normalized_value): item
        for item in observations
        if item.observation_type in relation_by_type
    }
    assertion_ids: list[str] = []
    collected_target_events: dict[str, str] = {}
    seen: set[tuple[str, str, str]] = set()
    for known_case in known_cases:
        target_case_id = str(known_case.get("case_id", ""))
        target_url = str(known_case.get("final_url_display", ""))
        known_observations = known_case.get("observations")
        if not target_case_id or not target_url or not isinstance(known_observations, list):
            continue
        for raw_known in known_observations:
            if not isinstance(raw_known, dict):
                continue
            observation_type = str(raw_known.get("observation_type", ""))
            normalized_value = str(raw_known.get("normalized_value", ""))
            current = current_by_key.get((observation_type, normalized_value))
            relation = relation_by_type.get(observation_type)
            if current is None or relation is None:
                continue
            match_key = (target_case_id, relation, normalized_value)
            if match_key in seen or len(assertion_ids) >= 12:
                continue
            seen.add(match_key)
            if target_case_id not in collected_target_events:
                collected = store.append_event(
                    case_id=case_id,
                    run_id=run_id,
                    kind="candidate_page.collected",
                    payload={
                        "lead_id": None,
                        "node_id": f"known-case:{target_case_id}",
                        "url": target_url,
                        "source_case_id": target_case_id,
                        "collection_source": "already_verified_local_case",
                        "artifact_id": raw_known.get("source_artifact_id"),
                    },
                    causation_event_id=causation_event_id,
                )
                collected_target_events[target_case_id] = collected.event_id
            match_event = store.append_event(
                case_id=case_id,
                run_id=run_id,
                kind="entity.matched",
                payload={
                    "observation_id": current.id,
                    "target_case_id": target_case_id,
                    "target_url": target_url,
                    "match_method": "exact_normalized_public_observable",
                    "observation_type": observation_type,
                    "normalized_value": normalized_value,
                    "target_observation_id": raw_known.get("id"),
                },
                causation_event_id=collected_target_events[target_case_id],
            )
            assertion_id = f"assertion-match-{uuid.uuid4().hex[:12]}"
            source_artifacts = [
                current.source_artifact_id,
                f"case:{target_case_id}:{raw_known.get('source_artifact_id', 'unknown')}",
            ]
            store.add_assertion(
                CandidateAssertion(
                    assertion_id=assertion_id,
                    case_id=case_id,
                    run_id=run_id,
                    assertion_type=relation,  # type: ignore[arg-type]
                    subject=source_url,
                    object=target_url,
                    supporting_observation_ids=[
                        current.id,
                        f"case:{target_case_id}:{raw_known.get('id', 'unknown')}",
                    ],
                    source_artifact_ids=source_artifacts,
                    created_at=datetime.now(UTC),
                    limitations=[
                        "Exact normalized public-observable equality supports only the stated "
                        "candidate relationship; it does not establish ownership or operator "
                        "identity."
                    ],
                ),
                causation_event_id=match_event.event_id,
            )
            assertion_ids.append(assertion_id)
    return assertion_ids


def _persist_temporal_comparison(
    *,
    store: InvestigationStore,
    case_id: str,
    run_id: str,
    source_url: str,
    observations: list[SemanticObservation],
    known_cases: list[dict[str, object]],
    causation_event_id: str,
) -> dict[str, object] | None:
    """Compare the current capture with the latest verified local capture of the same host."""

    source_host = _hostname(source_url)
    candidates = [
        item
        for item in known_cases
        if _hostname(str(item.get("final_url_display", ""))) == source_host
        and isinstance(item.get("observations"), list)
    ]
    if not candidates:
        return None
    previous = max(candidates, key=lambda item: str(item.get("completed_at", "")))
    previous_observations = previous.get("observations")
    if not isinstance(previous_observations, list):
        return None
    previous_values = {
        (str(item.get("observation_type", "")), str(item.get("normalized_value", "")))
        for item in previous_observations
        if isinstance(item, dict)
    }
    current_values = {(item.observation_type, item.normalized_value) for item in observations}
    added = sorted(current_values - previous_values)
    removed = sorted(previous_values - current_values)
    unchanged = current_values & previous_values
    payload: dict[str, object] = {
        "previous_case_id": previous.get("case_id"),
        "previous_completed_at": previous.get("completed_at"),
        "current_case_id": case_id,
        "hostname": source_host,
        "added_count": len(added),
        "removed_count": len(removed),
        "unchanged_count": len(unchanged),
        "added": [f"{kind}:{value}" for kind, value in added[:50]],
        "removed": [f"{kind}:{value}" for kind, value in removed[:50]],
        "comparison_scope": "exact_normalized_public_observations",
    }
    store.append_event(
        case_id=case_id,
        run_id=run_id,
        kind="temporal.snapshot.compared",
        payload=payload,
        causation_event_id=causation_event_id,
    )
    return payload


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
    interaction_index: int = 1,
    workspace_id: str,
    tool_name: str,
    progress_callback: LiveProgressCallback | None,
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
            browser = launch_chromium(playwright.chromium, headless=True)
            context = browser.new_context(
                accept_downloads=False,
                viewport={"width": 1440, "height": 1024},
                locale="id-ID",
                extra_http_headers={"Accept-Language": "id-ID,id;q=0.9,en;q=0.7"},
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
            popup_pages: list[Any] = []

            def record_popup(popup: Any) -> None:
                popup_pages.append(popup)
                popup.on("download", lambda download: download.cancel())

            page.on("popup", record_popup)
            page.on("download", lambda download: download.cancel())
            page.goto(source_url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(5_000)
            resolved, resolution = _wait_for_live_reference(page, reference)
            if resolved is None:
                browser.close()
                return {
                    "status": "stale_reference",
                    "reason": str(resolution.get("reason", "reference_not_resolved")),
                    "executed": False,
                    "resolution": resolution,
                }
            locator = resolved.locator
            observed_label = re.sub(r"\s+", " ", locator.inner_text(timeout=2_000)).strip()[:200]
            if reference.visible_text and not _reference_label_matches(
                reference.visible_text, observed_label
            ):
                browser.close()
                return {
                    "status": "stale_reference",
                    "reason": "visible_text_changed",
                    "executed": False,
                    "resolution": resolved.diagnostics,
                }
            locator.scroll_into_view_if_needed(timeout=3_000)
            target_bbox = locator.bounding_box(timeout=3_000)
            viewport = {"width": 1440, "height": 1024}
            before_screenshot = page.screenshot(full_page=False, timeout=5_000)
            before_screenshot_name = f"interaction-{interaction_index:03d}-before.png"
            (artifacts / before_screenshot_name).write_bytes(before_screenshot)
            _emit_live_progress(
                progress_callback,
                "agent_focus_ready",
                workspace_id=workspace_id,
                artifact_name=before_screenshot_name,
                label=reference.accessible_name,
                tool_name=tool_name,
                iteration=interaction_index,
                url=page.url,
                viewport_width=viewport["width"],
                viewport_height=viewport["height"],
                target_bbox=target_bbox,
                sha256=hashlib.sha256(before_screenshot).hexdigest(),
            )
            before_url = page.url
            navigation_surface = "same_page"
            direct_destination = element.destination_url or element.href
            if element.declared_behavior == "open_public_link" and direct_destination:
                destination_host = _hostname(direct_destination)
                if destination_host != source_host:
                    raise UnsafeUrlError("interaction navigation left the approved host")
                response = page.goto(
                    direct_destination,
                    wait_until="domcontentloaded",
                    timeout=30_000,
                )
                if response is not None and response.status >= 400:
                    raise RuntimeError(f"public route returned HTTP {response.status}")
            else:
                locator.click(timeout=5_000)
                page.wait_for_timeout(750)
                if len(popup_pages) > 1:
                    for popup in popup_pages:
                        popup.close()
                    raise RuntimeError("interaction opened multiple popup pages")
                if popup_pages:
                    popup = popup_pages[0]
                    popup.wait_for_load_state("domcontentloaded", timeout=30_000)
                    popup_target = safety_policy.validate_crawl_url(popup.url, refresh_dns=True)
                    if popup_target.hostname.removeprefix("www.") != source_host:
                        popup.close()
                        raise UnsafeUrlError("interaction popup left the approved host")
                    page = popup
                    navigation_surface = "same_origin_popup"
            route_fallback: str | None = None
            if navigation_surface == "same_page" and page.url == before_url:
                route_fallback = _contact_route_fallback(source_url, reference.accessible_name)
            if route_fallback is not None:
                safety_policy.validate_crawl_url(route_fallback, refresh_dns=True)
                response = page.goto(route_fallback, wait_until="domcontentloaded", timeout=30_000)
                if response is not None and response.status >= 400:
                    raise RuntimeError(f"contact route returned HTTP {response.status}")
                navigation_surface = "same_origin_fallback"
            render_readiness = _wait_for_interaction_render(page)
            final_url = page.url
            screenshot = page.screenshot(full_page=False, timeout=5_000)
            html = page.content()
            visible_text = page.locator("body").inner_text(timeout=5_000)
            screenshot_name = f"interaction-{interaction_index:03d}.png"
            state_name = f"interaction-{interaction_index:03d}.json"
            html_name = f"interaction-{interaction_index:03d}.html"
            visible_text_name = f"interaction-{interaction_index:03d}.txt"
            (artifacts / screenshot_name).write_bytes(screenshot)
            (artifacts / html_name).write_text(html, encoding="utf-8")
            (artifacts / visible_text_name).write_text(visible_text, encoding="utf-8")
            state = {
                "url": final_url,
                "title": page.title(),
                "visible_text_chars": len(visible_text),
                "html_sha256": hashlib.sha256(html.encode()).hexdigest(),
                "screenshot_sha256": hashlib.sha256(screenshot).hexdigest(),
                "request_count": request_count,
                "blocked_request_count": len(blocked_requests),
                "html_artifact": html_name,
                "visible_text_artifact": visible_text_name,
                "selected_element": reference.model_dump(mode="json"),
                "element_resolution": resolved.diagnostics,
                "target_bbox": target_bbox,
                "viewport": viewport,
                "before_screenshot_artifact": before_screenshot_name,
                "navigation_fallback": route_fallback,
                "navigation_surface": navigation_surface,
                "render_readiness": render_readiness,
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
        "before_screenshot_artifact": before_screenshot_name,
        "screenshot_artifact": screenshot_name,
        "html_artifact": html_name,
        "visible_text_artifact": visible_text_name,
        "request_count": request_count,
        "blocked_request_count": len(blocked_requests),
        "executed": True,
        "target_bbox": target_bbox,
        "viewport": viewport,
        "screenshot_sha256": hashlib.sha256(screenshot).hexdigest(),
        "resolution": resolved.diagnostics,
        "navigation_surface": navigation_surface,
        "render_readiness": render_readiness,
        "_html": html,
    }


def _wait_for_interaction_render(
    page: Any,
    *,
    attempts: int = 12,
    retry_delay_ms: int = 750,
) -> dict[str, object]:
    """Wait for bounded visible-text stability after a same-page or popup interaction."""

    previous_signature: str | None = None
    stable_samples = 0
    visible_text_chars = 0
    for attempt in range(1, attempts + 1):
        try:
            visible_text = re.sub(
                r"\s+", " ", page.locator("body").inner_text(timeout=3_000)
            ).strip()
        except Exception:
            visible_text = ""
        visible_text_chars = len(visible_text)
        signature = hashlib.sha256(visible_text.encode()).hexdigest() if visible_text else None
        if signature is not None and signature == previous_signature:
            stable_samples += 1
        else:
            stable_samples = 0
        previous_signature = signature
        if attempt >= 4 and visible_text_chars >= 40 and stable_samples >= 2:
            return {
                "status": "ready",
                "attempt": attempt,
                "max_attempts": attempts,
                "visible_text_chars": visible_text_chars,
                "stable_samples": stable_samples,
            }
        if attempt < attempts:
            page.wait_for_timeout(retry_delay_ms)
    return {
        "status": "limited",
        "attempt": attempts,
        "max_attempts": attempts,
        "visible_text_chars": visible_text_chars,
        "stable_samples": stable_samples,
    }


def _emit_live_progress(
    callback: LiveProgressCallback | None,
    stage: str,
    **detail: object,
) -> None:
    if callback is not None:
        callback(stage, detail)


def _contact_route_fallback(source_url: str, label: str) -> str | None:
    """Resolve a visible SPA contact control that did not expose a link target.

    This remains same-origin, is attempted only after the discovered control was clicked, and is
    limited to a conventional public-information route rather than arbitrary generated crawling.
    """

    if not _CONTACT_REVEAL.search(label):
        return None
    path = "/Help" if re.search(r"\b(help|support)\b", label, re.I) else "/Contact"
    parsed = urlsplit(source_url)
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _reference_label_matches(expected: str, observed: str) -> bool:
    if expected == observed:
        return True
    return bool(_CONTACT_REVEAL.search(expected) and _CONTACT_REVEAL.search(observed))


def _wait_for_live_reference(
    page: Any,
    reference: StableElementReference,
    *,
    attempts: int = 6,
    retry_delay_ms: int = 500,
) -> tuple[_ResolvedLiveReference | None, dict[str, object]]:
    """Resolve one issued reference after a dynamic page render, without guessing a target."""

    last_diagnostics: dict[str, object] = {"reason": "reference_not_resolved"}
    for attempt in range(1, attempts + 1):
        resolved, diagnostics = _resolve_live_reference(page, reference)
        diagnostics["attempt"] = attempt
        diagnostics["max_attempts"] = attempts
        if resolved is not None:
            resolved.diagnostics.update({"attempt": attempt, "max_attempts": attempts})
            return resolved, resolved.diagnostics
        last_diagnostics = diagnostics
        if attempt < attempts:
            page.wait_for_timeout(retry_delay_ms)
    return None, last_diagnostics


def _resolve_live_reference(
    page: Any, reference: StableElementReference
) -> tuple[_ResolvedLiveReference | None, dict[str, object]]:
    """Re-bind a server-issued reference to exactly one visible, semantically matching node.

    Dynamic sites commonly render duplicate desktop/mobile controls or rebuild their component
    tree between capture and execution. The original CSS path remains the first strategy, while
    role/name and bounded tag scans may recover the same issued reference. Every strategy verifies
    tag, visible/accessibility label, href, and action before returning a locator. Ambiguous visible
    matches always fail closed.
    """

    strategies: list[tuple[str, Any]] = [("css_path", page.locator(reference.dom_path))]
    if reference.role in {"link", "button"} and reference.accessible_name:
        strategies.append(
            (
                "role_and_accessible_name",
                page.get_by_role(reference.role, name=reference.accessible_name, exact=True),
            )
        )
    strategies.append(("tag_and_reference", page.locator(reference.tag)))

    attempts: list[dict[str, object]] = []
    ambiguous = False
    for strategy, locator in strategies:
        try:
            raw_candidates = locator.evaluate_all(_ELEMENT_RESOLUTION_JS)
        except Exception as error:
            attempts.append(
                {
                    "strategy": strategy,
                    "candidate_count": 0,
                    "matching_visible_count": 0,
                    "error": type(error).__name__,
                }
            )
            continue
        candidates = raw_candidates if isinstance(raw_candidates, list) else []
        matching_indices = [
            int(item["index"])
            for item in candidates
            if isinstance(item, dict)
            and isinstance(item.get("index"), int)
            and _live_candidate_matches(item, reference)
        ]
        attempt = {
            "strategy": strategy,
            "candidate_count": len(candidates),
            "matching_visible_count": len(matching_indices),
        }
        attempts.append(attempt)
        if len(matching_indices) == 1:
            diagnostics: dict[str, object] = {
                "strategy": strategy,
                "candidate_count": len(candidates),
                "matching_visible_count": 1,
                "attempts": attempts,
                "reason": "reference_resolved",
            }
            return (
                _ResolvedLiveReference(
                    locator=locator.nth(matching_indices[0]),
                    strategy=strategy,
                    diagnostics=diagnostics,
                ),
                diagnostics,
            )
        ambiguous = ambiguous or len(matching_indices) > 1

    return None, {
        "reason": "reference_ambiguous" if ambiguous else "reference_not_found",
        "attempts": attempts,
    }


def _live_candidate_matches(
    candidate: dict[str, object], reference: StableElementReference
) -> bool:
    if candidate.get("visible") is not True or candidate.get("tag") != reference.tag:
        return False
    text = str(candidate.get("text") or "")
    aria = str(candidate.get("aria") or "")
    observed_label = aria or text
    expected_labels = [reference.accessible_name, reference.visible_text]
    if not any(
        expected and _reference_label_matches(expected, observed_label)
        for expected in expected_labels
    ):
        return False
    observed_href = str(candidate.get("href") or "") or None
    if reference.href is not None and _comparable_url(observed_href or "") != _comparable_url(
        reference.href
    ):
        return False
    observed_action = str(candidate.get("action") or "") or None
    return reference.action is None or observed_action == reference.action


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
        "public_telegram_contact": 10,
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
    return sorted(
        candidates,
        key=lambda item: (
            _candidate_priority(_hostname(item.normalized_value), source_host, token),
            item.normalized_value,
        ),
    )


def _candidate_priority(target_host: str, source_host: str, token: str) -> int:
    """Prefer named product-family domains over affiliates, regional hosts, and corporate links."""

    if token and re.match(rf"^{re.escape(token)}(?:casino|poker|sport)\.", target_host):
        return 0
    if token and target_host.startswith(token):
        return 1
    if target_host.endswith(f".{source_host}"):
        return 3
    return 2


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
