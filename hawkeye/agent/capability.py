"""Secret-free bounded capability probes for the two allowed local codex-lb routes."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from .models import CapabilityDiagnostics, EndpointCapability

CODEX_LB_ENDPOINTS = (
    "http://127.0.0.1:2455/backend-api/codex",
    "http://127.0.0.1:2455/v1/responses",
)
_MAX_PROBE_BYTES = 64_000


def probe_codex_lb(
    *, timeout_seconds: float = 2.0, api_key: str | None = None
) -> CapabilityDiagnostics:
    """Probe only fixed loopback routes; unsupported features remain explicitly unknown."""

    if not 0 < timeout_seconds <= 5:
        raise ValueError("Capability-probe timeout must be greater than zero and at most 5 seconds")
    endpoints = [
        _probe_endpoint(endpoint, timeout_seconds, api_key=api_key)
        for endpoint in CODEX_LB_ENDPOINTS
    ]
    supported = next((item for item in endpoints if item.route_supported is True), None)
    safe_to_enable = bool(
        supported
        and supported.structured_output_support is True
        and supported.function_call_support is True
        and supported.tool_result_continuation is True
    )
    return CapabilityDiagnostics(
        generated_at=datetime.now(UTC),
        endpoints=endpoints,
        supported_route=supported.endpoint if supported else None,
        selected_model=supported.available_model if supported else None,
        safe_to_enable_model_path=safe_to_enable,
        fallback_required=not safe_to_enable,
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


def _probe_endpoint(
    endpoint: str, timeout_seconds: float, *, api_key: str | None
) -> EndpointCapability:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        endpoint,
        method="POST",
        data=b"{}",
        headers=headers,
    )
    started = time.monotonic()
    status: int | None = None
    content_type: str | None = None
    diagnostic = "no response"
    reachable = False
    route_supported: bool | None = None
    response_headers: dict[str, str] = {}
    body = b""
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            reachable = True
            status = response.status
            response_headers = {key.casefold(): value for key, value in response.headers.items()}
            body = response.read(_MAX_PROBE_BYTES)
            diagnostic = "loopback endpoint accepted a bounded empty POST probe"
            route_supported = status not in {404, 405}
    except urllib.error.HTTPError as error:
        reachable = True
        status = error.code
        response_headers = {key.casefold(): value for key, value in error.headers.items()}
        body = error.read(_MAX_PROBE_BYTES)
        route_supported = status not in {404, 405}
        diagnostic = f"loopback endpoint returned HTTP {status}"
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        diagnostic = f"loopback endpoint unavailable: {type(error).__name__}"
    latency_ms = max(0, round((time.monotonic() - started) * 1000))
    content_type = response_headers.get("content-type", "").split(";", maxsplit=1)[0] or None
    advertised = _advertised_capabilities(body, content_type)
    return EndpointCapability(
        endpoint=endpoint,
        reachable=reachable,
        http_status=status,
        route_supported=route_supported,
        available_model=_optional_string(advertised.get("model")),
        streaming_support=_optional_bool(advertised.get("streaming")),
        structured_output_support=_optional_bool(advertised.get("structured_output")),
        function_call_support=_optional_bool(advertised.get("function_calling")),
        tool_result_continuation=_optional_bool(advertised.get("tool_result_continuation")),
        cancellation_support=_optional_bool(advertised.get("cancellation")),
        timeout_behavior="bounded" if reachable else "unknown",
        native_search_support=_native_search(advertised.get("native_search")),
        native_search_source_url_visibility=_optional_bool(
            advertised.get("native_search_source_urls")
        ),
        response_content_type=content_type,
        latency_ms=latency_ms,
        diagnostic=diagnostic,
    )


def _advertised_capabilities(body: bytes, content_type: str | None) -> dict[str, object]:
    if content_type != "application/json" or not body:
        return {}
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    capability = payload.get("capabilities", payload)
    if not isinstance(capability, dict):
        return {}
    allowed = {
        "model",
        "streaming",
        "structured_output",
        "function_calling",
        "tool_result_continuation",
        "cancellation",
        "native_search",
        "native_search_source_urls",
    }
    return {str(key): value for key, value in capability.items() if str(key) in allowed}


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _native_search(
    value: object,
) -> Literal["supported_structured", "supported_unstructured", "unsupported", "unknown"]:
    valid = {"supported_structured", "supported_unstructured", "unsupported", "unknown"}
    if value in valid:
        return cast(
            Literal["supported_structured", "supported_unstructured", "unsupported", "unknown"],
            value,
        )
    return "unknown"


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None
