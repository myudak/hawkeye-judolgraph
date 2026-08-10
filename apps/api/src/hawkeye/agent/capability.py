"""Explicit, secret-free capability handshake for an OpenAI-compatible provider."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from .config import LlmConfig
from .investigator import OpenAICompatibleClient, ProviderHttpError
from .models import CapabilityDiagnostics, EndpointCapability


def probe_llm(config: LlmConfig) -> CapabilityDiagnostics:
    """Perform one opt-in strict JSON-schema handshake; never called by a page load."""

    started = time.monotonic()
    client = OpenAICompatibleClient(config)
    reachable = False
    supported = False
    diagnostic = "model provider unavailable"
    status: int | None = None
    try:
        result = client.request_structured(
            name="hawkeye_capability_probe",
            schema={
                "type": "object",
                "properties": {"ready": {"type": "boolean"}},
                "required": ["ready"],
                "additionalProperties": False,
            },
            system="Return only JSON matching the requested schema.",
            user="Return ready=true and no other fields.",
        )
        reachable = True
        supported = result == {"ready": True}
        status = 200
        diagnostic = (
            "strict JSON-schema handshake succeeded"
            if supported
            else "provider returned JSON that failed the handshake contract"
        )
    except (ProviderHttpError, RuntimeError, ValueError) as error:
        if isinstance(error, ProviderHttpError):
            reachable = True
            status = error.status
            diagnostic = f"model provider returned HTTP {error.status}"
        else:
            diagnostic = f"model provider unavailable: {type(error).__name__}"
    endpoint = client.last_endpoint or _preferred_endpoint(config)
    latency_ms = max(0, round((time.monotonic() - started) * 1000))
    capability = EndpointCapability(
        endpoint=endpoint,
        reachable=reachable,
        http_status=status,
        route_supported=supported if reachable else None,
        available_model=config.model if supported else None,
        structured_output_support=supported,
        timeout_behavior="bounded",
        response_content_type="application/json" if supported else None,
        latency_ms=latency_ms,
        diagnostic=diagnostic,
    )
    return CapabilityDiagnostics(
        generated_at=datetime.now(UTC),
        endpoints=[capability],
        supported_route=endpoint if supported else None,
        selected_model=config.model if supported else None,
        safe_to_enable_model_path=supported,
        fallback_required=not supported,
    )


def write_capability_diagnostics(
    diagnostics: CapabilityDiagnostics, output_path: Path | str
) -> Path:
    destination = Path(output_path).expanduser().resolve()
    if destination.exists():
        raise FileExistsError(f"Capability diagnostics already exist: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(diagnostics.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination


def _preferred_endpoint(config: LlmConfig) -> str:
    return config.endpoint(
        "chat/completions" if config.api_style == "chat_completions" else "responses"
    )
