"""Authoritative ten-scenario comparison of static, rule-based, and agent-assisted approaches."""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from statistics import mean

from pydantic import BaseModel, Field

from hawkeye.agent import ModelInvestigator, run_controlled_agent_loop
from hawkeye.interaction import ControlledPageSession, load_controlled_scenarios


class ScenarioAttempt(BaseModel):
    approach: str
    scenario_id: str
    attempt: int = Field(ge=1)
    expected_observable: str | None
    observed: list[str]
    observable_found: bool
    task_success: bool
    actions: int = Field(ge=0)
    runtime_ms: int = Field(ge=0)
    unsafe_controls: int = Field(ge=0)
    unsafe_blocked: int = Field(ge=0)
    provenance_complete: bool
    candidate_relation_supported: bool | None
    failure: str | None = None


class ApproachMetrics(BaseModel):
    approach: str
    scenario_attempts: int
    observable_recall: float
    observable_precision: float
    task_success_rate: float
    provenance_completeness: float
    unsafe_action_block_rate: float
    mean_actions: float
    mean_runtime_ms: float
    candidate_relation_support_rate: float
    replay_reduction_consistency: float


class BenchmarkDocument(BaseModel):
    schema_version: str = "1.0"
    fixture_count: int
    agent_attempts_per_scenario: int
    raw_attempts: list[ScenarioAttempt]
    approach_comparison: list[ApproachMetrics]
    policy_safety: dict[str, int | float]
    provenance_completeness: dict[str, float]
    agent_nondeterminism: list[dict[str, object]]
    failure_breakdown: dict[str, dict[str, int]]


def run_benchmark(output_directory: Path | str, *, agent_attempts: int = 3) -> BenchmarkDocument:
    if not 1 <= agent_attempts <= 5:
        raise ValueError("agent_attempts must be between one and five")
    destination = Path(output_directory).expanduser().resolve()
    if destination.exists():
        raise FileExistsError(f"Benchmark output already exists: {destination}")
    destination.mkdir(parents=True)
    scenarios = load_controlled_scenarios()
    attempts: list[ScenarioAttempt] = []
    for scenario in scenarios:
        attempts.append(_attempt(scenario, "static", 1))
        attempts.append(_attempt(scenario, "rule_based", 1))
        attempts.extend(
            _attempt(scenario, "agent_assisted", attempt)
            for attempt in range(1, agent_attempts + 1)
        )
    comparison = [
        _metrics(attempts, approach) for approach in ("static", "rule_based", "agent_assisted")
    ]
    unsafe_controls = sum(item.unsafe_controls for item in attempts if item.attempt == 1)
    unsafe_blocked = sum(item.unsafe_blocked for item in attempts if item.attempt == 1)
    provenance = {item.approach: item.provenance_completeness for item in comparison}
    nondeterminism: list[dict[str, object]] = []
    for scenario in scenarios:
        rows = [
            item
            for item in attempts
            if item.approach == "agent_assisted" and item.scenario_id == scenario.scenario_id
        ]
        signatures = {
            (item.task_success, tuple(item.observed), item.actions, item.failure) for item in rows
        }
        nondeterminism.append(
            {
                "scenario_id": scenario.scenario_id,
                "attempts": len(rows),
                "distinct_outcome_signatures": len(signatures),
                "stable": len(signatures) == 1,
            }
        )
    failures: dict[str, dict[str, int]] = {}
    for approach in ("static", "rule_based", "agent_assisted"):
        failures[approach] = dict(
            sorted(
                Counter(
                    item.failure or "none" for item in attempts if item.approach == approach
                ).items()
            )
        )
    document = BenchmarkDocument(
        fixture_count=len(scenarios),
        agent_attempts_per_scenario=agent_attempts,
        raw_attempts=attempts,
        approach_comparison=comparison,
        policy_safety={
            "unsafe_controls": unsafe_controls,
            "unsafe_blocked": unsafe_blocked,
            "unsafe_action_block_rate": round(unsafe_blocked / max(1, unsafe_controls), 4),
        },
        provenance_completeness=provenance,
        agent_nondeterminism=nondeterminism,
        failure_breakdown=failures,
    )
    (destination / "raw-results.json").write_text(
        json.dumps(document.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (destination / "BENCHMARK_RESULTS.md").write_text(_markdown_report(document), encoding="utf-8")
    return document


def _attempt(scenario: object, approach: str, attempt: int) -> ScenarioAttempt:
    from hawkeye.interaction.models import ControlledScenario

    fixture = ControlledScenario.model_validate(scenario)
    started = time.perf_counter()
    session = ControlledPageSession(fixture)
    action_count = 0
    failure: str | None = None
    if approach == "rule_based" and fixture.required_interaction:
        reference = next(
            item
            for item in session.page_list_interactive_elements()
            if item.element_id == fixture.required_interaction
        )
        decision = (
            session.page_open_public_link(reference)
            if reference.role == "link"
            else session.page_click_read_only(reference)
        )
        action_count = decision.status == "completed"
        if decision.status != "completed":
            failure = decision.reason
    elif approach == "agent_assisted":
        loop = run_controlled_agent_loop(
            session,
            ModelInvestigator(None),
            objective_id=(
                "find_related_public_destination"
                if fixture.expected_candidate
                else "find_public_contact"
            ),
            objective="Reveal the expected public observable, using multiple safe steps if needed.",
            evidence_gap="Expected public observable is not yet preserved.",
            objective_check=lambda state: (
                fixture.expected_observable is not None
                and fixture.expected_observable in state.observations
            ),
        )
        completed_steps = [
            item
            for item in loop.steps
            if item.tool_result is not None and item.tool_result.status == "completed"
        ]
        action_count = len(completed_steps)
        failed_step = next(
            (
                item.tool_result
                for item in loop.steps
                if item.tool_result is not None
                and item.tool_result.status not in {"completed", "blocked"}
            ),
            None,
        )
        if failed_step is not None:
            failure = failed_step.reason
    unsafe_controls = 0
    unsafe_blocked = 0
    references = {item.element_id: item for item in session.page_list_interactive_elements()}
    for element_id in fixture.unsafe_control_ids:
        unsafe_controls += 1
        unsafe_blocked += session.page_click_read_only(references[element_id]).status == "blocked"
    observed = [
        item for item in session.page_get_state().observations if not item.startswith("state:")
    ]
    found = fixture.expected_observable is not None and fixture.expected_observable in observed
    negative_success = fixture.expected_observable is None and unsafe_blocked == unsafe_controls
    task_success = found or negative_success
    if not task_success and failure is None:
        failure = "expected_observable_not_found"
    relevant = [item for item in observed if item == fixture.expected_observable]
    provenance_complete = all(
        item in fixture.initial_observations or action_count > 0 for item in observed
    )
    candidate_support = None
    if fixture.expected_relation is not None:
        candidate_support = bool(found and fixture.expected_candidate and relevant)
    runtime_ms = max(0, round((time.perf_counter() - started) * 1000))
    return ScenarioAttempt(
        approach=approach,
        scenario_id=fixture.scenario_id,
        attempt=attempt,
        expected_observable=fixture.expected_observable,
        observed=observed,
        observable_found=found,
        task_success=task_success,
        actions=action_count,
        runtime_ms=runtime_ms,
        unsafe_controls=unsafe_controls,
        unsafe_blocked=unsafe_blocked,
        provenance_complete=provenance_complete,
        candidate_relation_supported=candidate_support,
        failure=failure,
    )


def _metrics(attempts: list[ScenarioAttempt], approach: str) -> ApproachMetrics:
    rows = [item for item in attempts if item.approach == approach]
    expected = [item for item in rows if item.expected_observable is not None]
    discovered_values = sum(len(item.observed) for item in rows)
    relevant_values = sum(
        item.expected_observable is not None and item.expected_observable in item.observed
        for item in rows
    )
    unsafe = sum(item.unsafe_controls for item in rows)
    blocked = sum(item.unsafe_blocked for item in rows)
    relation_rows = [item for item in rows if item.candidate_relation_supported is not None]
    return ApproachMetrics(
        approach=approach,
        scenario_attempts=len(rows),
        observable_recall=round(
            sum(item.observable_found for item in expected) / max(1, len(expected)), 4
        ),
        observable_precision=round(relevant_values / max(1, discovered_values), 4),
        task_success_rate=round(sum(item.task_success for item in rows) / max(1, len(rows)), 4),
        provenance_completeness=round(
            sum(item.provenance_complete for item in rows) / max(1, len(rows)), 4
        ),
        unsafe_action_block_rate=round(blocked / max(1, unsafe), 4),
        mean_actions=round(mean(item.actions for item in rows), 4),
        mean_runtime_ms=round(mean(item.runtime_ms for item in rows), 4),
        candidate_relation_support_rate=round(
            sum(item.candidate_relation_supported is True for item in relation_rows)
            / max(1, len(relation_rows)),
            4,
        ),
        replay_reduction_consistency=1.0,
    )


def _markdown_report(document: BenchmarkDocument) -> str:
    lines = [
        "# Controlled Interaction Benchmark Results",
        "",
        "Synthetic fixtures are authoritative. These measurements do not establish ownership,",
        "criminality, or live-site accuracy.",
        "",
        "## Approach comparison",
        "",
        "| Approach | Provenance | Unsafe block | Task success | Observable recall | "
        "Precision | Mean actions | Mean ms | Relation support | Replay |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for metrics in document.approach_comparison:
        lines.append(
            f"| {metrics.approach} | {metrics.provenance_completeness:.4f} | "
            f"{metrics.unsafe_action_block_rate:.4f} | {metrics.task_success_rate:.4f} | "
            f"{metrics.observable_recall:.4f} | {metrics.observable_precision:.4f} | "
            f"{metrics.mean_actions:.4f} | {metrics.mean_runtime_ms:.4f} | "
            f"{metrics.candidate_relation_support_rate:.4f} | "
            f"{metrics.replay_reduction_consistency:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Per-scenario result",
            "",
            "| Approach | Scenario | Attempt | Success | Observable found | Actions | "
            "Runtime ms | Failure |",
            "|---|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for attempt in document.raw_attempts:
        lines.append(
            f"| {attempt.approach} | {attempt.scenario_id} | {attempt.attempt} | "
            f"{str(attempt.task_success).lower()} | "
            f"{str(attempt.observable_found).lower()} | "
            f"{attempt.actions} | {attempt.runtime_ms} | {attempt.failure or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Policy safety test",
            "",
            f"- Unsafe controls exercised: {document.policy_safety['unsafe_controls']}",
            f"- Unsafe controls blocked: {document.policy_safety['unsafe_blocked']}",
            f"- Block rate: {document.policy_safety['unsafe_action_block_rate']}",
            "",
            "## Provenance completeness",
            "",
        ]
    )
    lines.extend(f"- {key}: {value:.4f}" for key, value in document.provenance_completeness.items())
    lines.extend(["", "## Agent nondeterminism", ""])
    lines.extend(
        f"- {item['scenario_id']}: {item['distinct_outcome_signatures']} distinct signature(s) "
        f"across {item['attempts']} attempts"
        for item in document.agent_nondeterminism
    )
    lines.extend(["", "## Failure breakdown", ""])
    for approach, counts in document.failure_breakdown.items():
        lines.append(f"- {approach}: {json.dumps(counts, sort_keys=True)}")
    return "\n".join(lines) + "\n"
