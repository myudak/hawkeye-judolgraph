"""Focused CodexInvestigator with schema validation and deterministic fallback."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Literal

from pydantic import ValidationError

from hawkeye.interaction.models import InteractiveElement, StableElementReference
from hawkeye.interaction.policy import validate_read_only_interaction

from .models import AgentDecision, AgentFailure, AgentStepResult, AgentVisibleContext


class CodexLbClient:
    """Bounded localhost transport with no browser, filesystem, database, or shell handle."""

    def __init__(
        self,
        endpoint: str,
        *,
        model: str | None,
        timeout_seconds: float = 10.0,
        api_key: str | None = None,
    ) -> None:
        if endpoint not in {
            "http://127.0.0.1:2455/backend-api/codex",
            "http://127.0.0.1:2455/v1/responses",
        }:
            raise ValueError("Codex endpoint must be one of the fixed loopback routes")
        if not 0 < timeout_seconds <= 30:
            raise ValueError("Codex request timeout must be greater than zero and at most 30")
        self.endpoint = endpoint
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._api_key = api_key

    def request_decision(self, context: AgentVisibleContext) -> object:
        schema = _strict_json_schema(AgentDecision.model_json_schema())
        request_payload: dict[str, object] = {
            "input": [
                {
                    "role": "system",
                    "content": (
                        "Return only one JSON value matching the supplied schema. Choose at most "
                        "one bounded tool request, assertion proposal, or stop. Never infer "
                        "ownership "
                        "or criminality."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        context.model_dump(mode="json"),
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                },
            ],
            "stream": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "agent_decision",
                    "strict": True,
                    "schema": schema,
                }
            },
        }
        if self.model:
            request_payload["model"] = self.model
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        request = urllib.request.Request(
            self.endpoint,
            method="POST",
            data=json.dumps(request_payload).encode("utf-8"),
            headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                body = response.read(256_000)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise RuntimeError(f"codex-lb request failed: {type(error).__name__}") from error
        payload = json.loads(body)
        structured = _structured_response(payload)
        if structured is not None:
            return structured
        raise ValueError("codex-lb did not return validated structured output")


class DeterministicInvestigator:
    """Fixture-capable fallback producing the same AgentDecision schema as Codex."""

    def choose(self, context: AgentVisibleContext) -> AgentDecision:
        ranked = sorted(context.safe_interactive_elements, key=_fallback_priority)
        for reference in ranked:
            pseudo_element = _reference_policy_projection(reference)
            permitted, _, _ = validate_read_only_interaction(pseudo_element)
            if not permitted:
                continue
            tool: Literal["page_open_public_link", "page_click_read_only"] = (
                "page_open_public_link" if reference.role == "link" else "page_click_read_only"
            )
            return AgentDecision(
                action="tool_request",
                tool_name=tool,
                element_reference=reference,
                outcome_summary=(
                    "Deterministic fallback selected the first policy-permitted public action."
                ),
            )
        return AgentDecision(
            action="stop",
            outcome_summary=(
                "Evidence is sufficient for the bounded objective."
                if context.normalized_observations
                else "No policy-permitted action can close the explicit evidence gap."
            ),
        )


def _fallback_priority(reference: StableElementReference) -> tuple[int, str]:
    label = f"{reference.accessible_name} {reference.visible_text}".casefold()
    priorities = (
        ("contact us", 0),
        ("hubungi", 0),
        ("kontak", 0),
        ("contact", 0),
        ("support", 1),
        ("help", 1),
        ("about", 2),
        ("information", 2),
        ("public", 3),
        ("promotion", 4),
        ("promo", 4),
        ("menu", 5),
    )
    score = next((value for term, value in priorities if term in label), 10)
    return score, reference.element_id


class CodexInvestigator:
    """Validate model output and fail closed to deterministic selection after bounded attempts."""

    def __init__(
        self,
        client: CodexLbClient | None,
        *,
        fallback: DeterministicInvestigator | None = None,
        request_override: Callable[[AgentVisibleContext], object] | None = None,
    ) -> None:
        self.client = client
        self.fallback = fallback or DeterministicInvestigator()
        self.request_override = request_override

    def choose(self, context: AgentVisibleContext) -> AgentStepResult:
        failures: list[AgentFailure] = []
        requester = self.request_override or (
            self.client.request_decision if self.client is not None else None
        )
        if requester is None:
            failures.append(
                AgentFailure(
                    attempt=1,
                    category="endpoint_unavailable",
                    message="No safe Codex capability was available.",
                    fallback_activated=True,
                )
            )
            return AgentStepResult(
                decision=self.fallback.choose(context),
                mode="deterministic_fallback",
                failures=failures,
            )
        for attempt in range(1, 3):
            try:
                raw = requester(context)
                decision = AgentDecision.model_validate(raw)
                _validate_context_decision(decision, context)
                return AgentStepResult(decision=decision, mode="codex", failures=failures)
            except ValidationError as error:
                failures.append(
                    AgentFailure(
                        attempt=attempt,
                        category="invalid_schema",
                        message=str(error)[:1000],
                        fallback_activated=attempt == 2,
                    )
                )
            except (ValueError, json.JSONDecodeError) as error:
                failures.append(
                    AgentFailure(
                        attempt=attempt,
                        category="invalid_schema",
                        message=str(error)[:1000],
                        fallback_activated=attempt == 2,
                    )
                )
            except RuntimeError as error:
                failures.append(
                    AgentFailure(
                        attempt=attempt,
                        category="transport_error",
                        message=str(error)[:1000],
                        fallback_activated=attempt == 2,
                    )
                )
        return AgentStepResult(
            decision=self.fallback.choose(context),
            mode="deterministic_fallback",
            failures=failures,
        )


def _reference_policy_projection(reference: object) -> InteractiveElement:
    item = StableElementReference.model_validate(reference)
    behavior: Literal["open_public_link", "reveal_modal"] = (
        "open_public_link" if item.role == "link" and item.href else "reveal_modal"
    )
    return InteractiveElement(
        element_id=item.element_id,
        dom_path=item.dom_path,
        role=item.role,
        tag=item.tag,
        accessible_name=item.accessible_name,
        visible_text=item.visible_text,
        href=item.href,
        action=item.action,
        declared_behavior=behavior,
        destination_url=item.href,
    )


def _structured_response(payload: object) -> dict[str, object] | None:
    """Read only schema-requested JSON fields from supported response envelopes."""

    if not isinstance(payload, dict):
        return None
    parsed = payload.get("output_parsed")
    if isinstance(parsed, dict):
        return parsed
    output = payload.get("output")
    if not isinstance(output, list):
        return None
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "output_text":
                continue
            text = block.get("text")
            if not isinstance(text, str) or len(text) > 64_000:
                continue
            try:
                decoded = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(decoded, dict):
                return decoded
    return None


def _strict_json_schema(value: object) -> object:
    """Make Pydantic's nullable defaults compatible with strict Responses schemas."""

    if isinstance(value, list):
        return [_strict_json_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    projected = {key: _strict_json_schema(item) for key, item in value.items() if key != "default"}
    properties = projected.get("properties")
    if projected.get("type") == "object" and isinstance(properties, dict):
        projected["additionalProperties"] = False
        projected["required"] = list(properties)
    return projected


def _validate_context_decision(decision: AgentDecision, context: AgentVisibleContext) -> None:
    """Bind a model-selected tool request to an exact server-issued safe reference."""

    if decision.action != "tool_request":
        return
    if decision.element_reference is None or decision.tool_name is None:
        raise ValueError("tool request omitted its bounded reference or tool name")
    expected = next(
        (
            item
            for item in context.safe_interactive_elements
            if item.reference_id == decision.element_reference.reference_id
        ),
        None,
    )
    if expected is None or expected != decision.element_reference:
        raise ValueError("tool request did not preserve an issued safe element reference")
