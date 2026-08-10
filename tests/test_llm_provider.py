"""OpenAI-compatible transport tests: strict envelopes, fallback routing, and secret hygiene."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from hawkeye.agent import LlmConfig, OpenAICompatibleClient
from hawkeye.agent.investigator import ProviderHttpError
from hawkeye.agent.models import AgentVisibleContext
from hawkeye.interaction.models import InteractionBudget

ProviderResponse = tuple[int, dict[str, str], bytes]


def _context() -> AgentVisibleContext:
    return AgentVisibleContext(
        objective="Stop safely when no interaction is needed.",
        current_case_state={"objective_satisfied": True},
        normalized_observations=[],
        safe_interactive_elements=[],
        policy_budget=InteractionBudget(),
        evidence_gap="none",
    )


def _decision_body(*, chat: bool) -> bytes:
    decision = json.dumps(
        {
            "action": "stop",
            "outcome_summary": "The bounded objective is satisfied.",
            "objective_satisfied": True,
            "stop_reason": "objective_satisfied",
        }
    )
    payload = (
        {"choices": [{"message": {"content": decision}}]}
        if chat
        else {"output_parsed": json.loads(decision)}
    )
    return json.dumps(payload).encode()


@contextmanager
def _provider_server(
    responder: Callable[[str, bytes, dict[str, str]], ProviderResponse],
) -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            status, headers, response_body = responder(
                self.path,
                body,
                {key.casefold(): value for key, value in self.headers.items()},
            )
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            try:
                self.wfile.write(response_body)
            except (BrokenPipeError, ConnectionResetError):
                return

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_missing_environment_configuration_means_fallback_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "HAWKEYE_LLM_BASE_URL",
        "HAWKEYE_LLM_MODEL",
        "HAWKEYE_LLM_API_KEY",
        "CODEX_BASE_URL",
        "CODEX_MODEL",
        "CODEX_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    assert LlmConfig.from_environment() is None


def test_remote_plain_http_provider_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires HTTPS"):
        LlmConfig(base_url="http://model.example/v1", model="fixture")


def test_chat_completions_strict_success_and_authorization_is_request_only() -> None:
    observed: dict[str, str] = {}

    def responder(path: str, _body: bytes, headers: dict[str, str]) -> ProviderResponse:
        observed["path"] = path
        observed["authorization"] = headers.get("authorization", "")
        return 200, {"Content-Type": "application/json"}, _decision_body(chat=True)

    with _provider_server(responder) as root:
        client = OpenAICompatibleClient(
            LlmConfig(
                base_url=root,
                model="fixture",
                api_style="chat_completions",
                api_key="secret-value",
            )
        )
        result = client.request_decision(_context())
    assert isinstance(result, dict) and result["action"] == "stop"
    assert observed == {
        "path": "/v1/chat/completions",
        "authorization": "Bearer secret-value",
    }
    assert "secret-value" not in repr(client.config)


def test_auto_switches_only_when_responses_route_is_missing() -> None:
    paths: list[str] = []

    def responder(path: str, _body: bytes, _headers: dict[str, str]) -> ProviderResponse:
        paths.append(path)
        if path.endswith("/responses"):
            return 404, {"Content-Type": "application/json"}, b"{}"
        return 200, {"Content-Type": "application/json"}, _decision_body(chat=True)

    with _provider_server(responder) as root:
        result = OpenAICompatibleClient(
            LlmConfig(base_url=root, model="fixture", api_style="auto")
        ).request_decision(_context())
    assert isinstance(result, dict) and result["action"] == "stop"
    assert paths == ["/v1/responses", "/v1/chat/completions"]


def test_auto_does_not_mask_schema_or_general_http_errors() -> None:
    paths: list[str] = []

    def responder(path: str, _body: bytes, _headers: dict[str, str]) -> ProviderResponse:
        paths.append(path)
        return 400, {"Content-Type": "application/json"}, b"{}"

    with _provider_server(responder) as root:
        client = OpenAICompatibleClient(LlmConfig(base_url=root, model="fixture"))
        with pytest.raises(ProviderHttpError) as error:
            client.request_decision(_context())
    assert error.value.status == 400
    assert paths == ["/v1/responses"]


def test_redirect_is_rejected_without_forwarding_credentials() -> None:
    def responder(_path: str, _body: bytes, _headers: dict[str, str]) -> ProviderResponse:
        return 307, {"Location": "https://attacker.invalid/v1/responses"}, b""

    with _provider_server(responder) as root:
        client = OpenAICompatibleClient(
            LlmConfig(base_url=root, model="fixture", api_key="do-not-forward")
        )
        with pytest.raises(ProviderHttpError) as error:
            client.request_decision(_context())
    assert error.value.status == 307
    assert "do-not-forward" not in str(error.value)


def test_timeout_and_oversized_response_fail_closed() -> None:
    def slow(_path: str, _body: bytes, _headers: dict[str, str]) -> ProviderResponse:
        time.sleep(0.1)
        return 200, {"Content-Type": "application/json"}, _decision_body(chat=False)

    with _provider_server(slow) as root:
        client = OpenAICompatibleClient(
            LlmConfig(base_url=root, model="fixture", timeout_seconds=0.01)
        )
        with pytest.raises(RuntimeError, match="request failed"):
            client.request_decision(_context())

    def large(_path: str, _body: bytes, _headers: dict[str, str]) -> ProviderResponse:
        return 200, {"Content-Type": "application/json"}, b"x" * 256_001

    with _provider_server(large) as root:
        client = OpenAICompatibleClient(LlmConfig(base_url=root, model="fixture"))
        with pytest.raises(RuntimeError, match="bounded size"):
            client.request_decision(_context())
