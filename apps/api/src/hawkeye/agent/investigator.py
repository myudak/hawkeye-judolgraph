"""Provider-neutral model investigator with strict output validation and safe fallback."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Literal

from pydantic import ValidationError

from hawkeye.interaction.models import InteractiveElement, StableElementReference
from hawkeye.interaction.policy import validate_read_only_interaction

from .config import LlmConfig
from .models import AgentDecision, AgentFailure, AgentStepResult, AgentVisibleContext

_MAX_RESPONSE_BYTES = 256_000


class ProviderHttpError(RuntimeError):
    def __init__(self, status: int) -> None:
        super().__init__(f"model provider returned HTTP {status}")
        self.status = status


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> None:
        return None


class OpenAICompatibleClient:
    """Bounded OpenAI-compatible transport with no browser, filesystem, or shell handle."""

    def __init__(self, config: LlmConfig) -> None:
        self.config = config
        self.model = config.model
        self._opener = urllib.request.build_opener(_NoRedirect)
        self.last_endpoint: str | None = None

    def request_decision(self, context: AgentVisibleContext) -> object:
        return self.request_structured(
            name="agent_decision",
            schema=_strict_json_schema(AgentDecision.model_json_schema()),
            system=(
                "Return only one JSON value matching the supplied schema. Choose at most one "
                "bounded tool request, assertion proposal, or stop. Never infer ownership or "
                "criminality."
            ),
            user=json.dumps(
                context.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            ),
        )

    def request_structured(
        self,
        *,
        name: str,
        schema: object,
        system: str,
        user: str,
    ) -> object:
        styles = (
            ("responses", "chat_completions")
            if self.config.api_style == "auto"
            else (self.config.api_style,)
        )
        last_error: ProviderHttpError | None = None
        for index, style in enumerate(styles):
            try:
                if style == "responses":
                    payload = self._responses_payload(name, schema, system, user)
                    response = self._post_json(self.config.endpoint("responses"), payload)
                    structured = _structured_responses_output(response)
                else:
                    payload = self._chat_payload(name, schema, system, user)
                    response = self._post_json(self.config.endpoint("chat/completions"), payload)
                    structured = _structured_chat_output(response)
            except ProviderHttpError as error:
                last_error = error
                can_switch = (
                    self.config.api_style == "auto" and index == 0 and error.status in {404, 405}
                )
                if can_switch:
                    continue
                raise
            if structured is None:
                raise ValueError("model provider did not return the requested structured output")
            self.last_endpoint = self.config.endpoint(
                "responses" if style == "responses" else "chat/completions"
            )
            return structured
        assert last_error is not None
        raise last_error

    def _responses_payload(
        self, name: str, schema: object, system: str, user: str
    ) -> dict[str, object]:
        return {
            "model": self.model,
            "input": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": name,
                    "strict": True,
                    "schema": schema,
                }
            },
        }

    def _chat_payload(self, name: str, schema: object, system: str, user: str) -> dict[str, object]:
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": name, "strict": True, "schema": schema},
            },
        }

    def _post_json(self, endpoint: str, payload: object) -> object:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        request = urllib.request.Request(
            endpoint,
            method="POST",
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers=headers,
        )
        try:
            with self._opener.open(request, timeout=self.config.timeout_seconds) as response:
                body = response.read(_MAX_RESPONSE_BYTES + 1)
                content_type = response.headers.get_content_type()
        except urllib.error.HTTPError as error:
            raise ProviderHttpError(error.code) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise RuntimeError(f"model provider request failed: {type(error).__name__}") from error
        if len(body) > _MAX_RESPONSE_BYTES:
            raise RuntimeError("model provider response exceeded the bounded size limit")
        if content_type != "application/json":
            raise ValueError("model provider response was not application/json")
        try:
            return json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("model provider returned invalid JSON") from error


class DeterministicInvestigator:
    """Fixture-capable fallback producing the same AgentDecision schema as the model."""

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
                "The bounded objective is already satisfied."
                if context.current_case_state.get("objective_satisfied") is True
                else "No policy-permitted action can close the explicit evidence gap."
            ),
            objective_satisfied=context.current_case_state.get("objective_satisfied") is True,
            stop_reason=(
                "objective_satisfied"
                if context.current_case_state.get("objective_satisfied") is True
                else "no_safe_action"
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


class ModelInvestigator:
    """Validate model output and fail closed to deterministic selection after bounded attempts."""

    def __init__(
        self,
        client: OpenAICompatibleClient | None,
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
                    message="No validated model configuration was available.",
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
                return AgentStepResult(decision=decision, mode="model", failures=failures)
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


def _structured_responses_output(payload: object) -> dict[str, object] | None:
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
            decoded = _json_object(block.get("text"))
            if decoded is not None:
                return decoded
    return None


def _structured_chat_output(payload: object) -> dict[str, object] | None:
    if not isinstance(payload, dict) or not isinstance(payload.get("choices"), list):
        return None
    for choice in payload["choices"]:
        if not isinstance(choice, dict) or not isinstance(choice.get("message"), dict):
            continue
        decoded = _json_object(choice["message"].get("content"))
        if decoded is not None:
            return decoded
    return None


def _json_object(value: object) -> dict[str, object] | None:
    if not isinstance(value, str) or len(value) > 64_000:
        return None
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, dict) else None


def _strict_json_schema(value: object) -> object:
    """Make Pydantic's nullable defaults compatible with strict provider schemas."""

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
