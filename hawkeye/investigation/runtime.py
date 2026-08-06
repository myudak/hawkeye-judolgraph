"""Canonical deterministic synthetic Page A to Page B investigation runtime."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel

from hawkeye.agent import AgentVisibleContext, CodexInvestigator
from hawkeye.interaction import ControlledPageSession, load_controlled_scenarios

from .models import CandidateAssertion, CandidateLead, ProgressiveGraphState
from .reducer import reduce_events
from .store import InvestigationStore


class FixtureInvestigationResult(BaseModel):
    case_id: str
    run_id: str
    directory: str
    database_path: str
    assertion_id: str | None
    lead_status: str | None
    agent_mode: str
    graph: ProgressiveGraphState


def run_fixture_investigation(
    scenario_id: str,
    output_directory: Path | str,
    *,
    collection_mode: str = "synthetic_fixture",
    investigator: CodexInvestigator | None = None,
) -> FixtureInvestigationResult:
    scenarios = {item.scenario_id: item for item in load_controlled_scenarios()}
    if scenario_id not in scenarios:
        raise ValueError(f"Unknown controlled scenario: {scenario_id}")
    if collection_mode not in {"synthetic_fixture", "real_world"}:
        raise ValueError("collection_mode must be synthetic_fixture or real_world")
    scenario = scenarios[scenario_id]
    destination = Path(output_directory).expanduser().resolve()
    if destination.exists():
        raise FileExistsError(f"Investigation output already exists: {destination}")
    destination.mkdir(parents=True)
    artifacts = destination / "artifacts"
    artifacts.mkdir()
    case_id = f"fixture-{scenario.scenario_id}"
    run_id = f"run-{uuid.uuid4().hex}"
    store = InvestigationStore(destination / "investigation.sqlite3")
    started = store.append_event(
        case_id=case_id,
        run_id=run_id,
        kind="run.started",
        payload={"seed_url": scenario.seed_url, "collection_mode": collection_mode},
    )
    collection = store.append_event(
        case_id=case_id,
        run_id=run_id,
        kind="collection.started",
        payload={"page": "A"},
        causation_event_id=started.event_id,
    )
    page_a_path, page_a_hash = _write_fixture_artifact(
        artifacts / "page-a.json",
        {"url": scenario.seed_url, "observations": scenario.initial_observations},
    )
    captured = store.append_event(
        case_id=case_id,
        run_id=run_id,
        kind="artifact.captured",
        payload={
            "artifact_id": "artifact-page-a",
            "node_id": "page:a",
            "label": scenario.seed_url,
            "path": page_a_path,
            "sha256": page_a_hash,
        },
        causation_event_id=collection.event_id,
    )
    observation_ids: list[str] = []
    for index, value in enumerate(scenario.initial_observations, start=1):
        observation_id = f"obs-page-a-{index:03d}"
        observation_ids.append(observation_id)
        store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind="observation.created",
            payload={
                "observation_id": observation_id,
                "node_id": f"observation:{observation_id}",
                "source_node_id": "page:a",
                "observation_type": _fixture_observation_type(value),
                "normalized_value": value,
                "artifact_id": "artifact-page-a",
            },
            causation_event_id=captured.event_id,
        )
    session = ControlledPageSession(scenario)
    gap = store.append_event(
        case_id=case_id,
        run_id=run_id,
        kind="evidence_gap.created",
        payload={"gap": "required public observable not yet preserved"},
        causation_event_id=captured.event_id,
    )
    objective = store.append_event(
        case_id=case_id,
        run_id=run_id,
        kind="agent.objective.created",
        payload={"objective": "Close one explicit evidence gap using at most one safe action."},
        causation_event_id=gap.event_id,
    )
    context = AgentVisibleContext(
        objective="Close one explicit evidence gap using at most one safe action.",
        current_case_state={"case_id": case_id, "capture_adequacy": "adequate"},
        normalized_observations=session.page_get_state().observations,
        safe_interactive_elements=session.page_list_interactive_elements(),
        policy_budget=session.budget,
        evidence_gap="required public observable not yet preserved",
    )
    references = {item.element_id: item for item in context.safe_interactive_elements}
    for element_id in scenario.unsafe_control_ids:
        reference = references[element_id]
        requested_preflight = store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind="tool.requested",
            payload={
                "action": "policy_preflight",
                "tool_name": "page_click_read_only",
                "element_reference": reference.model_dump(mode="json"),
                "outcome_summary": "Validate a controlled prohibited action without execution.",
                "executed": False,
            },
            causation_event_id=objective.event_id,
        )
        preflight = session.page_click_read_only(reference)
        if preflight.status != "blocked":
            raise ValueError("Controlled unsafe-action preflight was not blocked")
        store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind="tool.blocked",
            payload={
                **preflight.model_dump(mode="json"),
                "element_id": element_id,
                "policy_preflight": True,
                "executed": False,
            },
            causation_event_id=requested_preflight.event_id,
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
    if step.decision.action == "tool_request" and step.decision.element_reference is not None:
        requested = store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind="tool.requested",
            payload=step.decision.model_dump(mode="json"),
            causation_event_id=objective.event_id,
        )
        tool_result = (
            session.page_open_public_link(step.decision.element_reference)
            if step.decision.tool_name == "page_open_public_link"
            else session.page_click_read_only(step.decision.element_reference)
        )
        completed = store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind="tool.completed" if tool_result.status == "completed" else "tool.blocked",
            payload=tool_result.model_dump(mode="json"),
            causation_event_id=requested.event_id,
        )
        new_values = sorted(set(tool_result.observations) - set(scenario.initial_observations))
        for index, value in enumerate(new_values, start=1):
            observation_id = f"obs-page-a-interaction-{index:03d}"
            observation_ids.append(observation_id)
            store.append_event(
                case_id=case_id,
                run_id=run_id,
                kind="observation.created",
                payload={
                    "observation_id": observation_id,
                    "node_id": f"observation:{observation_id}",
                    "source_node_id": "page:a",
                    "observation_type": _fixture_observation_type(value),
                    "normalized_value": value,
                    "artifact_id": "artifact-page-a",
                },
                causation_event_id=completed.event_id,
            )
    assertion_id: str | None = None
    lead_status: str | None = None
    if scenario.expected_candidate:
        _validate_synthetic_public_url(scenario.expected_candidate)
        search = store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind="search.started",
            payload={"strategy": "direct_observable_then_fixture_index"},
            causation_event_id=objective.event_id,
        )
        synthetic = collection_mode == "synthetic_fixture"
        lead = CandidateLead(
            lead_id=f"lead-{scenario.ordinal:02d}",
            case_id=case_id,
            run_id=run_id,
            url=scenario.expected_candidate,
            discovery_method="fixture_index" if synthetic else "direct_link",
            source_observation_ids=observation_ids,
            collection_mode=collection_mode,  # type: ignore[arg-type]
            initial_status="approved_for_recollection" if synthetic else "waiting_for_approval",
            created_at=datetime.now(UTC),
        )
        store.add_lead(lead, causation_event_id=search.event_id)
        selected = store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind="candidate_page.selected",
            payload={"lead_id": lead.lead_id, "url": lead.url},
            causation_event_id=search.event_id,
        )
        if not synthetic:
            store.append_event(
                case_id=case_id,
                run_id=run_id,
                kind="candidate_page.approval_required",
                payload={"lead_id": lead.lead_id, "url": lead.url},
                causation_event_id=selected.event_id,
            )
            lead_status = "waiting_for_approval"
        else:
            page_b_observation = _candidate_observation(scenario.expected_relation)
            page_b_path, page_b_hash = _write_fixture_artifact(
                artifacts / "page-b.json",
                {"url": scenario.expected_candidate, "observations": [page_b_observation]},
            )
            collected_b = store.append_event(
                case_id=case_id,
                run_id=run_id,
                kind="candidate_page.collected",
                payload={
                    "lead_id": lead.lead_id,
                    "node_id": "page:b",
                    "url": lead.url,
                    "artifact_id": "artifact-page-b",
                    "path": page_b_path,
                    "sha256": page_b_hash,
                },
                causation_event_id=selected.event_id,
            )
            page_b_observation_id = "obs-page-b-001"
            store.append_event(
                case_id=case_id,
                run_id=run_id,
                kind="observation.created",
                payload={
                    "observation_id": page_b_observation_id,
                    "node_id": f"observation:{page_b_observation_id}",
                    "source_node_id": "page:b",
                    "observation_type": _fixture_observation_type(page_b_observation),
                    "normalized_value": page_b_observation,
                    "artifact_id": "artifact-page-b",
                },
                causation_event_id=collected_b.event_id,
            )
            assertion_id = f"assertion-{scenario.ordinal:02d}"
            store.add_assertion(
                CandidateAssertion(
                    assertion_id=assertion_id,
                    case_id=case_id,
                    run_id=run_id,
                    assertion_type=scenario.expected_relation or "candidate_related_to",  # type: ignore[arg-type]
                    subject=scenario.seed_url,
                    object=scenario.expected_candidate,
                    supporting_observation_ids=[*observation_ids, page_b_observation_id],
                    source_artifact_ids=["artifact-page-a", "artifact-page-b"],
                    created_at=datetime.now(UTC),
                    limitations=[
                        "verified review would support only the stated relationship, not ownership"
                    ],
                ),
                causation_event_id=collected_b.event_id,
            )
            lead_status = "recollected"
    if lead_status != "waiting_for_approval":
        store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind="run.completed",
            payload={"assertion_id": assertion_id, "lead_status": lead_status},
        )
    graph = reduce_events(store.events(run_id))
    summary = FixtureInvestigationResult(
        case_id=case_id,
        run_id=run_id,
        directory=str(destination),
        database_path=str(store.path),
        assertion_id=assertion_id,
        lead_status=lead_status,
        agent_mode=step.mode,
        graph=graph,
    )
    (destination / "run-summary.json").write_text(
        json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def recollect_approved_fixture_candidate(
    output_directory: Path | str,
) -> FixtureInvestigationResult:
    """Finish an approval-gated controlled run without making a network request."""

    destination = Path(output_directory).expanduser().resolve()
    summary_path = destination / "run-summary.json"
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    summary = FixtureInvestigationResult.model_validate(payload)
    scenario_id = summary.case_id.removeprefix("fixture-")
    scenarios = {item.scenario_id: item for item in load_controlled_scenarios()}
    scenario = scenarios.get(scenario_id)
    if scenario is None or scenario.expected_candidate is None:
        raise ValueError("Approval-gated run has no controlled Page B candidate")
    _validate_synthetic_public_url(scenario.expected_candidate)
    store = InvestigationStore(destination / "investigation.sqlite3")
    events = store.events(summary.run_id)
    approval = next(
        (item for item in reversed(events) if item.kind == "candidate_page.approved"), None
    )
    if approval is None:
        raise ValueError("Page B recollection requires an explicit approval event")
    if any(item.kind == "candidate_page.collected" for item in events):
        raise ValueError("Page B was already recollected")
    lead_id = str(approval.payload.get("lead_id", f"lead-{scenario.ordinal:02d}"))
    page_b_observation = _candidate_observation(scenario.expected_relation)
    page_b_path, page_b_hash = _write_fixture_artifact(
        destination / "artifacts" / "page-b.json",
        {"url": scenario.expected_candidate, "observations": [page_b_observation]},
    )
    collected = store.append_event(
        case_id=summary.case_id,
        run_id=summary.run_id,
        kind="candidate_page.collected",
        payload={
            "lead_id": lead_id,
            "node_id": "page:b",
            "url": scenario.expected_candidate,
            "artifact_id": "artifact-page-b",
            "path": page_b_path,
            "sha256": page_b_hash,
        },
        causation_event_id=approval.event_id,
    )
    page_b_observation_id = "obs-page-b-001"
    store.append_event(
        case_id=summary.case_id,
        run_id=summary.run_id,
        kind="observation.created",
        payload={
            "observation_id": page_b_observation_id,
            "node_id": f"observation:{page_b_observation_id}",
            "source_node_id": "page:b",
            "observation_type": _fixture_observation_type(page_b_observation),
            "normalized_value": page_b_observation,
            "artifact_id": "artifact-page-b",
        },
        causation_event_id=collected.event_id,
    )
    page_a_observation_ids = [
        str(item.payload["observation_id"])
        for item in events
        if item.kind == "observation.created" and "observation_id" in item.payload
    ]
    assertion_id = f"assertion-{scenario.ordinal:02d}"
    store.add_assertion(
        CandidateAssertion(
            assertion_id=assertion_id,
            case_id=summary.case_id,
            run_id=summary.run_id,
            assertion_type=scenario.expected_relation or "candidate_related_to",  # type: ignore[arg-type]
            subject=scenario.seed_url,
            object=scenario.expected_candidate,
            supporting_observation_ids=[*page_a_observation_ids, page_b_observation_id],
            source_artifact_ids=["artifact-page-a", "artifact-page-b"],
            created_at=datetime.now(UTC),
            limitations=[
                "verified review would support only the stated relationship, not ownership"
            ],
        ),
        causation_event_id=collected.event_id,
    )
    store.append_event(
        case_id=summary.case_id,
        run_id=summary.run_id,
        kind="run.completed",
        payload={"assertion_id": assertion_id, "lead_status": "recollected"},
    )
    completed = summary.model_copy(
        update={
            "assertion_id": assertion_id,
            "lead_status": "recollected",
            "graph": reduce_events(store.events(summary.run_id)),
        }
    )
    summary_path.write_text(
        json.dumps(completed.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return completed


def _write_fixture_artifact(path: Path, payload: dict[str, object]) -> tuple[str, str]:
    content = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    path.write_bytes(content)
    return path.as_posix(), hashlib.sha256(content).hexdigest()


def _validate_synthetic_public_url(url: str) -> None:
    split = urlsplit(url)
    if (
        split.scheme not in {"http", "https"}
        or not split.hostname
        or split.username
        or split.password
    ):
        raise ValueError("Synthetic candidate URL failed lexical public URL policy")
    if not split.hostname.endswith(".invalid"):
        raise ValueError("Synthetic fixture candidate must use the reserved .invalid suffix")


def _fixture_observation_type(value: str) -> str:
    prefix = value.split(":", maxsplit=1)[0]
    return {
        "telegram": "public_telegram_alias",
        "email": "public_email_address",
        "phone": "public_phone_number",
        "link": "public_outgoing_link",
        "redirect": "public_redirect_target",
        "referral": "public_referral_code",
    }.get(prefix, "public_outgoing_link")


def _candidate_observation(relation: str | None) -> str:
    return {
        "shares_public_contact_with": "phone:+628111111111",
        "shares_redirect_target_with": "redirect:https://candidate-f.example.invalid/final",
        "shares_download_destination_with": "download:https://downloads.example.invalid/app.apk",
        "shares_referral_code_with": "referral:UNIQUE-TAB-4",
        "publicly_links_to": "link:https://source.example.invalid/",
        "claims_brand": "brand:example-public-service",
    }.get(relation or "", "link:https://source.example.invalid/")
