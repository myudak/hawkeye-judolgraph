"""Local bounded MVP workspace over synthetic runs and append-only human reviews."""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path

from hawkeye.agent import CodexInvestigator, CodexLbClient, probe_codex_lb
from hawkeye.agent.models import CapabilityDiagnostics
from hawkeye.interaction import load_controlled_scenarios
from hawkeye.investigation import (
    InvestigationStore,
    recollect_approved_fixture_candidate,
    reduce_events,
    run_fixture_investigation,
)

_RUN_ID = re.compile(r"^run-[a-z0-9-]{1,80}-[0-9a-f]{8}$")


class MvpWorkspace:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._capability_diagnostics: CapabilityDiagnostics | None = None
        self._investigator: CodexInvestigator | None = None

    def capability_status(self) -> dict[str, object]:
        """Return one cached, secret-free probe and prepare the gated model client."""

        if self._capability_diagnostics is None:
            api_key = os.environ.get("HAWKEYE_CODEX_LB_API_KEY")
            diagnostics = probe_codex_lb(timeout_seconds=0.75, api_key=api_key)
            self._capability_diagnostics = diagnostics
            probe_directory = self.root / "capability-probes"
            probe_directory.mkdir(exist_ok=True)
            probe_path = probe_directory / f"probe-{uuid.uuid4().hex[:12]}.json"
            probe_path.write_text(
                json.dumps(diagnostics.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            if diagnostics.safe_to_enable_model_path and diagnostics.supported_route is not None:
                self._investigator = CodexInvestigator(
                    CodexLbClient(
                        diagnostics.supported_route,
                        model=diagnostics.selected_model,
                        api_key=api_key,
                    )
                )
        diagnostics = self._capability_diagnostics
        assert diagnostics is not None
        reachable = any(item.reachable for item in diagnostics.endpoints)
        state = (
            "codex_ready"
            if diagnostics.safe_to_enable_model_path
            else "capability_unverified"
            if reachable
            else "endpoint_unavailable"
        )
        return {"state": state, **diagnostics.model_dump(mode="json")}

    def scenarios(self) -> list[dict[str, object]]:
        return [
            {
                "scenario_id": item.scenario_id,
                "ordinal": item.ordinal,
                "name": item.name,
                "seed_url": item.seed_url,
                "expected_observable": item.expected_observable,
                "unsafe_control_count": len(item.unsafe_control_ids),
            }
            for item in load_controlled_scenarios()
        ]

    def create_run(self, scenario_id: str, *, collection_mode: str) -> dict[str, object]:
        run_directory_id = f"run-{scenario_id}-{uuid.uuid4().hex[:8]}"
        if not _RUN_ID.fullmatch(run_directory_id):
            raise ValueError("Scenario ID cannot be used as a bounded workspace directory")
        self.capability_status()
        result = run_fixture_investigation(
            scenario_id,
            self.root / run_directory_id,
            collection_mode=collection_mode,
            investigator=self._investigator,
        )
        return {"workspace_id": run_directory_id, **result.model_dump(mode="json")}

    def list_runs(self) -> list[dict[str, object]]:
        runs: list[dict[str, object]] = []
        for directory in sorted(self.root.iterdir(), reverse=True):
            if not directory.is_dir() or not _RUN_ID.fullmatch(directory.name):
                continue
            summary_path = directory / "run-summary.json"
            try:
                payload = json.loads(summary_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                runs.append(
                    {
                        "workspace_id": directory.name,
                        "case_id": payload.get("case_id"),
                        "run_id": payload.get("run_id"),
                        "lead_status": payload.get("lead_status"),
                        "assertion_id": payload.get("assertion_id"),
                        "agent_mode": payload.get("agent_mode"),
                    }
                )
        return runs

    def details(self, workspace_id: str) -> dict[str, object]:
        directory = self._directory(workspace_id)
        summary = json.loads((directory / "run-summary.json").read_text(encoding="utf-8"))
        if not isinstance(summary, dict) or not isinstance(summary.get("run_id"), str):
            raise ValueError("Workspace run summary is invalid")
        store = InvestigationStore(directory / "investigation.sqlite3")
        events = store.events(summary["run_id"])
        graph = reduce_events(events)
        assertion_id = summary.get("assertion_id")
        assertion: dict[str, object] | None = None
        reviews: list[dict[str, object]] = []
        current_status: str | None = None
        if isinstance(assertion_id, str):
            assertion = store.assertion(assertion_id).model_dump(mode="json")
            reviews = [item.model_dump(mode="json") for item in store.review_history(assertion_id)]
            current_status = store.current_assertion_status(assertion_id)
        lead_status = summary.get("lead_status")
        if any(event.kind == "candidate_page.approved" for event in events) and not any(
            event.kind == "candidate_page.collected" for event in events
        ):
            lead_status = "approved_waiting_for_manual_collection"
        return {
            "workspace_id": workspace_id,
            "case_id": summary.get("case_id"),
            "run_id": summary["run_id"],
            "agent_mode": summary.get("agent_mode"),
            "lead_status": lead_status,
            "assertion": assertion,
            "current_assertion_status": current_status,
            "reviews": reviews,
            "events": [_event_for_ui(item.model_dump(mode="json")) for item in events],
            "graph": _graph_for_ui(graph.model_dump(mode="json")),
            "artifacts": [
                {"name": path.name, "bytes": path.stat().st_size}
                for path in sorted((directory / "artifacts").glob("*.json"))
            ],
        }

    def review(
        self,
        workspace_id: str,
        *,
        assertion_id: str,
        outcome: str,
        reviewer_label: str,
        reason: str,
    ) -> dict[str, object]:
        directory = self._directory(workspace_id)
        store = InvestigationStore(directory / "investigation.sqlite3")
        review = store.append_review(
            assertion_id,
            outcome=outcome,
            reviewer_label=reviewer_label,
            reason=reason,
        )
        return review.model_dump(mode="json")

    def approve_recollection(self, workspace_id: str) -> dict[str, object]:
        directory = self._directory(workspace_id)
        summary = json.loads((directory / "run-summary.json").read_text(encoding="utf-8"))
        store = InvestigationStore(directory / "investigation.sqlite3")
        run_id = str(summary["run_id"])
        case_id = str(summary["case_id"])
        events = store.events(run_id)
        required = next(
            (
                event
                for event in reversed(events)
                if event.kind == "candidate_page.approval_required"
            ),
            None,
        )
        if required is None:
            raise ValueError("This run has no candidate awaiting recollection approval")
        approved = store.append_event(
            case_id=case_id,
            run_id=run_id,
            kind="candidate_page.approved",
            payload={
                "lead_id": required.payload.get("lead_id"),
                "url": required.payload.get("url"),
                "note": "Approval recorded; controlled Page B recollection may now proceed.",
            },
            causation_event_id=required.event_id,
        )
        completed = recollect_approved_fixture_candidate(directory)
        return {
            "approval": approved.model_dump(mode="json"),
            "result": completed.model_dump(mode="json"),
        }

    def artifact(self, workspace_id: str, artifact_name: str) -> bytes:
        if artifact_name not in {"page-a.json", "page-b.json"}:
            raise ValueError("Unknown bounded MVP artifact")
        path = (self._directory(workspace_id) / "artifacts" / artifact_name).resolve()
        if not path.is_file():
            raise FileNotFoundError(artifact_name)
        return path.read_bytes()

    def _directory(self, workspace_id: str) -> Path:
        if not _RUN_ID.fullmatch(workspace_id):
            raise ValueError("Invalid workspace run ID")
        directory = (self.root / workspace_id).resolve()
        if directory.parent != self.root or not directory.is_dir():
            raise ValueError("Unknown workspace run")
        return directory


def _event_for_ui(event: dict[str, object]) -> dict[str, object]:
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return event
    return {**event, "payload": _payload_for_ui(payload)}


def _payload_for_ui(payload: dict[str, object]) -> dict[str, object]:
    projected = dict(payload)
    path = projected.get("path")
    if isinstance(path, str):
        projected["path"] = f"artifacts/{Path(path).name}"
    return projected


def _graph_for_ui(graph: dict[str, object]) -> dict[str, object]:
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        return graph
    projected_nodes: list[object] = []
    for item in nodes:
        if not isinstance(item, dict):
            projected_nodes.append(item)
            continue
        attributes = item.get("attributes")
        projected_nodes.append(
            {
                **item,
                "attributes": _payload_for_ui(attributes)
                if isinstance(attributes, dict)
                else attributes,
            }
        )
    timeline = graph.get("timeline")
    projected_timeline = (
        [_event_for_ui(item) if isinstance(item, dict) else item for item in timeline]
        if isinstance(timeline, list)
        else timeline
    )
    return {**graph, "nodes": projected_nodes, "timeline": projected_timeline}
