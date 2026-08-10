"""Validated runtime configuration for an OpenAI-compatible model provider."""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

ApiStyle = Literal["auto", "responses", "chat_completions"]


@dataclass(frozen=True, slots=True)
class LlmConfig:
    """Operator-owned model configuration; the API key is never included in repr/output."""

    base_url: str
    model: str
    api_style: ApiStyle = "auto"
    timeout_seconds: float = 15.0
    api_key: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        normalized = _validate_base_url(self.base_url)
        object.__setattr__(self, "base_url", normalized)
        if not self.model.strip() or len(self.model) > 200:
            raise ValueError("HAWKEYE_LLM_MODEL must be a non-empty model identifier")
        object.__setattr__(self, "model", self.model.strip())
        if self.api_style not in {"auto", "responses", "chat_completions"}:
            raise ValueError("HAWKEYE_LLM_API_STYLE must be auto, responses, or chat_completions")
        if not 0 < self.timeout_seconds <= 60:
            raise ValueError("HAWKEYE_LLM_TIMEOUT_SECONDS must be greater than 0 and at most 60")

    @classmethod
    def from_environment(cls) -> LlmConfig | None:
        """Read config without making a network request.

        CODEX_* aliases are accepted for local Codex-compatible gateways while the provider-
        neutral HAWKEYE_LLM_* names remain the documented contract.
        """

        base_url = _first_env("HAWKEYE_LLM_BASE_URL", "CODEX_BASE_URL")
        model = _first_env("HAWKEYE_LLM_MODEL", "CODEX_MODEL")
        api_key = _first_env("HAWKEYE_LLM_API_KEY", "CODEX_API_KEY")
        style = os.environ.get("HAWKEYE_LLM_API_STYLE", "auto").strip() or "auto"
        timeout_text = os.environ.get("HAWKEYE_LLM_TIMEOUT_SECONDS", "15").strip() or "15"
        if not base_url and not model and not api_key:
            return None
        if not base_url or not model:
            raise ValueError("HAWKEYE_LLM_BASE_URL and HAWKEYE_LLM_MODEL must both be configured")
        try:
            timeout = float(timeout_text)
        except ValueError as error:
            raise ValueError("HAWKEYE_LLM_TIMEOUT_SECONDS must be numeric") from error
        return cls(
            base_url=base_url,
            model=model,
            api_style=style,  # type: ignore[arg-type]
            timeout_seconds=timeout,
            api_key=api_key,
        )

    def endpoint(self, resource: Literal["responses", "chat/completions"]) -> str:
        return f"{self.base_url}/{resource}"


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    return None


def _validate_base_url(value: str) -> str:
    if len(value) > 2048:
        raise ValueError("HAWKEYE_LLM_BASE_URL is too long")
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("HAWKEYE_LLM_BASE_URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("HAWKEYE_LLM_BASE_URL cannot contain credentials, query, or fragment")
    if parsed.scheme != "https" and not _is_loopback_host(parsed.hostname):
        raise ValueError("HAWKEYE_LLM_BASE_URL requires HTTPS except for loopback development")
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _is_loopback_host(hostname: str) -> bool:
    normalized = hostname.casefold().rstrip(".")
    if normalized == "localhost" or normalized.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False
