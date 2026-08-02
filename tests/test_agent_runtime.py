"""G6 capability probing, strict schema, and deterministic fallback tests."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from hawkeye.agent import CodexInvestigator
from hawkeye.agent.models import AgentVisibleContext
from hawkeye.interaction import ControlledPageSession, load_controlled_scenarios


def _context(scenario_index: int = 1) -> AgentVisibleContext:
    session = ControlledPageSession(load_controlled_scenarios()[scenario_index])
    return AgentVisibleContext(
        objective="Reveal one public observable without unsafe interaction.",
        current_case_state={"case_id": "fixture", "status": "adequate"},
        normalized_observations=session.page_get_state().observations,
        safe_interactive_elements=session.page_list_interactive_elements(),
        policy_budget=session.budget,
        evidence_gap="The expected public observable is not visible yet.",
    )


def test_valid_structured_model_decision_is_accepted_without_execution() -> None:
    context = _context()
    reference = context.safe_interactive_elements[0]
    investigator = CodexInvestigator(
        None,
        request_override=lambda _context: {
            "action": "tool_request",
            "tool_name": "page_click_read_only",
            "element_reference": reference.model_dump(mode="json"),
            "outcome_summary": "Request one server-validated public reveal.",
        },
    )
    result = investigator.choose(context)
    assert result.mode == "codex"
    assert result.decision.tool_name == "page_click_read_only"
    assert result.failures == []


def test_free_form_or_invalid_schema_falls_back_after_two_attempts() -> None:
    calls = 0

    def invalid(_context: AgentVisibleContext) -> object:
        nonlocal calls
        calls += 1
        return "click the button"

    result = CodexInvestigator(None, request_override=invalid).choose(_context())
    assert calls == 2
    assert result.mode == "deterministic_fallback"
    assert result.decision.action == "tool_request"
    assert [item.category for item in result.failures] == ["invalid_schema", "invalid_schema"]
    assert result.failures[-1].fallback_activated is True


def test_model_cannot_mutate_an_issued_safe_reference() -> None:
    context = _context()
    reference = context.safe_interactive_elements[0].model_copy(
        update={"dom_path": "button#invented"}
    )
    calls = 0

    def mutated(_context: AgentVisibleContext) -> object:
        nonlocal calls
        calls += 1
        return {
            "action": "tool_request",
            "tool_name": "page_click_read_only",
            "element_reference": reference.model_dump(mode="json"),
            "outcome_summary": "Attempt a mutated selector.",
        }

    result = CodexInvestigator(None, request_override=mutated).choose(context)

    assert calls == 2
    assert result.mode == "deterministic_fallback"
    assert [item.category for item in result.failures] == [
        "invalid_schema",
        "invalid_schema",
    ]


def test_unavailable_endpoint_uses_same_normalized_decision_shape() -> None:
    result = CodexInvestigator(None).choose(_context())
    assert result.mode == "deterministic_fallback"
    assert result.decision.model_dump(mode="json")["action"] == "tool_request"
    assert result.raw_response_persisted is False


@contextmanager
def _capability_server() -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            body = json.dumps(
                {
                    "capabilities": {
                        "model": "fixture-model",
                        "streaming": True,
                        "structured_output": True,
                        "function_calling": True,
                        "tool_result_continuation": True,
                        "cancellation": True,
                        "native_search": "unsupported",
                        "native_search_source_urls": False,
                    }
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_capability_probe_uses_advertised_features_and_preserves_no_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import hawkeye.agent.capability as capability

    with _capability_server() as root:
        monkeypatch.setattr(capability, "CODEX_LB_ENDPOINTS", (f"{root}/one", f"{root}/two"))
        diagnostics = capability.probe_codex_lb(timeout_seconds=1)
    assert diagnostics.supported_route == f"{root}/one"
    assert diagnostics.selected_model == "fixture-model"
    assert diagnostics.safe_to_enable_model_path is True
    assert diagnostics.fallback_required is False
    assert diagnostics.secrets_persisted is False
    assert diagnostics.endpoints[0].native_search_support == "unsupported"
