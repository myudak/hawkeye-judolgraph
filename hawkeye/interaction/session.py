"""Deterministic executor exposing only narrow, policy-validated page tools."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from .models import (
    ControlledPageState,
    ControlledScenario,
    InteractionBudget,
    InteractionDecision,
    InteractiveElement,
    StableElementReference,
)
from .policy import validate_read_only_interaction


class ControlledPageSession:
    """Stateful fixture executor with stale-reference and budget enforcement."""

    def __init__(
        self, scenario: ControlledScenario, *, budget: InteractionBudget | None = None
    ) -> None:
        self.scenario = scenario
        self.budget = budget or InteractionBudget()
        self._observations = list(scenario.initial_observations)
        self._interaction_count = 0
        self._page_count = 1
        self._snapshot_sequence = 1
        self._started_at = datetime.now(UTC)
        self._url = scenario.seed_url
        self._executed_element_ids: set[str] = set()

    @property
    def snapshot_id(self) -> str:
        return f"snapshot-{self._snapshot_sequence:03d}"

    def page_get_state(self) -> ControlledPageState:
        return ControlledPageState(
            scenario_id=self.scenario.scenario_id,
            url=self._url,
            snapshot_id=self.snapshot_id,
            observations=sorted(set(self._observations)),
            interaction_count=self._interaction_count,
            page_count=self._page_count,
            redirect_chain=self.scenario.redirect_chain,
            available_element_ids=[
                item.element_id for item in self._available_elements(include_executed=False)
            ],
        )

    def page_list_interactive_elements(self) -> list[StableElementReference]:
        return [
            self._reference(element) for element in self._available_elements(include_executed=False)
        ]

    def page_click_read_only(self, reference: StableElementReference) -> InteractionDecision:
        return self._execute(reference, tool_name="page_click_read_only")

    def page_open_public_link(self, reference: StableElementReference) -> InteractionDecision:
        return self._execute(reference, tool_name="page_open_public_link", require_link=True)

    def page_capture_state(self) -> InteractionDecision:
        return InteractionDecision(
            status="completed",
            tool_name="page_capture_state",
            reason="normalized_state_captured",
            snapshot_id=self.snapshot_id,
            observations=sorted(set(self._observations)),
        )

    def page_get_redirect_chain(self) -> InteractionDecision:
        return InteractionDecision(
            status="completed",
            tool_name="page_get_redirect_chain",
            reason="redirect_chain_returned",
            snapshot_id=self.snapshot_id,
            observations=list(self.scenario.redirect_chain),
        )

    def _execute(
        self,
        reference: StableElementReference,
        *,
        tool_name: str,
        require_link: bool = False,
    ) -> InteractionDecision:
        before_snapshot = self.snapshot_id
        before_observations = set(self._observations)
        if reference.discovery_snapshot_id != self.snapshot_id:
            return self._decision(
                "stale_reference",
                tool_name,
                "discovery_snapshot_mismatch",
                before_snapshot_id=before_snapshot,
            )
        element = next(
            (
                item
                for item in self._available_elements(include_executed=False)
                if item.element_id == reference.element_id
            ),
            None,
        )
        if (
            element is None
            or self._reference(element).element_fingerprint != reference.element_fingerprint
        ):
            return self._decision(
                "stale_reference",
                tool_name,
                "element_fingerprint_mismatch",
                before_snapshot_id=before_snapshot,
            )
        if self._interaction_count >= self.budget.max_interactions:
            return self._decision(
                "budget_exhausted",
                tool_name,
                "interaction_budget_exhausted",
                before_snapshot_id=before_snapshot,
            )
        if require_link and element.declared_behavior != "open_public_link":
            return self._decision(
                "blocked",
                tool_name,
                "tool_requires_public_link",
                before_snapshot_id=before_snapshot,
            )
        permitted, reason, checks = validate_read_only_interaction(element)
        checks["interaction_count"] = self._interaction_count
        checks["max_interactions"] = self.budget.max_interactions
        checks["current_page_state"] = self.snapshot_id
        if not permitted:
            return self._decision(
                "blocked",
                tool_name,
                reason,
                policy_checks=checks,
                before_snapshot_id=before_snapshot,
            )
        self._interaction_count += 1
        self._executed_element_ids.add(element.element_id)
        self._observations.extend(element.reveals_observations)
        destination = element.destination_url or element.href
        if element.declared_behavior == "open_public_link" and destination:
            if self._page_count >= self.budget.max_pages:
                return self._decision(
                    "budget_exhausted",
                    tool_name,
                    "page_budget_exhausted",
                    before_snapshot_id=before_snapshot,
                )
            self._page_count += 1
            self._url = destination
        self._snapshot_sequence += 1
        after_observations = set(self._observations)
        return self._decision(
            "completed",
            tool_name,
            reason,
            destination_url=destination,
            policy_checks=checks,
            before_snapshot_id=before_snapshot,
            added_observations=sorted(after_observations - before_observations),
            removed_observations=sorted(before_observations - after_observations),
            state_changed=(
                after_observations != before_observations
                or self.snapshot_id != before_snapshot
                or destination is not None
            ),
        )

    def _available_elements(self, *, include_executed: bool) -> list[InteractiveElement]:
        observed = set(self._observations)
        return [
            item
            for item in self.scenario.elements
            if set(item.available_after).issubset(observed)
            and (include_executed or item.element_id not in self._executed_element_ids)
        ]

    def _reference(self, element: InteractiveElement) -> StableElementReference:
        payload = {
            "dom_path": element.dom_path,
            "role": element.role,
            "tag": element.tag,
            "accessible_name": element.accessible_name,
            "visible_text": element.visible_text,
            "href": element.href,
            "action": element.action,
            "snapshot": self.snapshot_id,
        }
        fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return StableElementReference(
            reference_id=f"ref-{element.element_id}-{self.snapshot_id}",
            discovery_snapshot_id=self.snapshot_id,
            element_id=element.element_id,
            dom_path=element.dom_path,
            role=element.role,
            tag=element.tag,
            accessible_name=element.accessible_name,
            visible_text=element.visible_text,
            href=element.href,
            action=element.action,
            element_fingerprint=fingerprint,
        )

    def _decision(
        self,
        status: str,
        tool_name: str,
        reason: str,
        *,
        destination_url: str | None = None,
        policy_checks: dict[str, object] | None = None,
        before_snapshot_id: str | None = None,
        added_observations: list[str] | None = None,
        removed_observations: list[str] | None = None,
        state_changed: bool = False,
    ) -> InteractionDecision:
        return InteractionDecision(
            status=status,  # type: ignore[arg-type]
            tool_name=tool_name,  # type: ignore[arg-type]
            reason=reason,
            snapshot_id=self.snapshot_id,
            observations=sorted(set(self._observations)),
            destination_url=destination_url,
            policy_checks=policy_checks or {},  # type: ignore[arg-type]
            before_snapshot_id=before_snapshot_id,
            added_observations=added_observations or [],
            removed_observations=removed_observations or [],
            state_changed=state_changed,
        )
