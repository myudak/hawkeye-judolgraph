"""Bounded multi-step tool loop with explicit objective and recovery semantics."""

from __future__ import annotations

from collections.abc import Callable

from hawkeye.interaction.models import ControlledPageState, InteractionDecision
from hawkeye.interaction.session import ControlledPageSession

from .investigator import ModelInvestigator
from .models import AgentLoopResult, AgentLoopStep, AgentVisibleContext

ObjectiveCheck = Callable[[ControlledPageState], bool]


def run_controlled_agent_loop(
    session: ControlledPageSession,
    investigator: ModelInvestigator,
    *,
    objective_id: str,
    objective: str,
    evidence_gap: str,
    objective_check: ObjectiveCheck,
) -> AgentLoopResult:
    """Run at most five model/fallback choices over narrow controlled tools.

    The session owns browser-like state and policy enforcement. The investigator sees only the
    normalized state and server-issued references. Stale or no-op results are fed back, never
    silently retried forever.
    """

    steps: list[AgentLoopStep] = []
    prior_results: list[InteractionDecision] = []
    attempted_reference_ids: list[str] = []
    stale_count = 0
    noop_count = 0

    for iteration in range(1, session.budget.max_iterations + 1):
        state = session.page_get_state()
        if objective_check(state):
            return _result(
                objective_id,
                steps,
                "objective_satisfied",
                True,
                state.observations,
            )
        context = AgentVisibleContext(
            objective=objective,
            objective_id=objective_id,  # type: ignore[arg-type]
            iteration=iteration,
            current_case_state={
                "case_id": state.scenario_id,
                "url": state.url,
                "snapshot_id": state.snapshot_id,
                "interaction_count": state.interaction_count,
                "page_count": state.page_count,
                "objective_satisfied": False,
            },
            normalized_observations=state.observations,
            safe_interactive_elements=session.page_list_interactive_elements(),
            policy_budget=session.budget,
            prior_tool_results=prior_results[-5:],
            evidence_gap=evidence_gap,
            attempted_reference_ids=attempted_reference_ids,
            latest_state_delta=(prior_results[-1].model_dump(mode="json") if prior_results else {}),
        )
        agent_step = investigator.choose(context)
        decision = agent_step.decision
        if decision.action == "stop":
            return _result(
                objective_id,
                steps,
                decision.stop_reason or "agent_stop",
                decision.objective_satisfied,
                state.observations,
            )
        if decision.action != "tool_request" or decision.element_reference is None:
            return _result(
                objective_id,
                steps,
                "insufficient_evidence",
                False,
                state.observations,
            )

        reference = decision.element_reference
        attempted_reference_ids.append(reference.reference_id)
        tool_result = (
            session.page_open_public_link(reference)
            if decision.tool_name == "page_open_public_link"
            else session.page_click_read_only(reference)
        )
        prior_results.append(tool_result)
        steps.append(AgentLoopStep(iteration=iteration, agent=agent_step, tool_result=tool_result))

        if tool_result.status == "budget_exhausted":
            return _result(
                objective_id,
                steps,
                "budget_exhausted",
                False,
                session.page_get_state().observations,
            )
        if tool_result.status == "stale_reference":
            stale_count += 1
            if stale_count >= 2:
                return _result(
                    objective_id,
                    steps,
                    "repeated_stale_reference",
                    False,
                    session.page_get_state().observations,
                )
            continue
        stale_count = 0
        if tool_result.status == "completed" and not tool_result.added_observations:
            noop_count += 1
            if noop_count >= 2:
                return _result(
                    objective_id,
                    steps,
                    "repeated_noop",
                    False,
                    session.page_get_state().observations,
                )
        else:
            noop_count = 0

    final_state = session.page_get_state()
    return _result(
        objective_id,
        steps,
        "objective_satisfied" if objective_check(final_state) else "max_iterations",
        objective_check(final_state),
        final_state.observations,
    )


def _result(
    objective_id: str,
    steps: list[AgentLoopStep],
    stop_reason: str,
    objective_satisfied: bool,
    observations: list[str],
) -> AgentLoopResult:
    return AgentLoopResult(
        objective_id=objective_id,
        steps=steps,
        stop_reason=stop_reason,  # type: ignore[arg-type]
        objective_satisfied=objective_satisfied,
        final_observations=sorted(set(observations)),
    )
