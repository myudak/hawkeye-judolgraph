"""Local desktop-only persistence for optional model-provider settings."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Literal

from hawkeye.agent import LlmConfig

_MANAGED_KEYS = (
    "HAWKEYE_LLM_ENABLED",
    "HAWKEYE_LLM_BASE_URL",
    "HAWKEYE_LLM_API_KEY",
    "HAWKEYE_LLM_MODEL",
    "HAWKEYE_LLM_API_STYLE",
    "HAWKEYE_LLM_TIMEOUT_SECONDS",
)


class DesktopSettingsStore:
    """Persist one local provider config without ever returning the API key."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path).expanduser().resolve()
        self._lock = threading.RLock()

    def view(self) -> dict[str, object]:
        with self._lock:
            values = self._effective_values()
            enabled_value = values.get("HAWKEYE_LLM_ENABLED")
            enabled = (
                enabled_value.strip().casefold() not in {"0", "false", "no", "off"}
                if enabled_value is not None
                else bool(values.get("HAWKEYE_LLM_BASE_URL"))
            )
            return {
                "available": True,
                "enabled": enabled,
                "base_url": values.get("HAWKEYE_LLM_BASE_URL", ""),
                "model": values.get("HAWKEYE_LLM_MODEL", ""),
                "api_style": values.get("HAWKEYE_LLM_API_STYLE", "auto"),
                "timeout_seconds": _safe_timeout(values.get("HAWKEYE_LLM_TIMEOUT_SECONDS")),
                "api_key_configured": bool(values.get("HAWKEYE_LLM_API_KEY")),
                "settings_path_display": "%LOCALAPPDATA%\\HAWK-EYE\\settings.env",
                "applies_to": "new_investigations",
            }

    def update(
        self,
        *,
        enabled: bool,
        base_url: str,
        model: str,
        api_style: Literal["auto", "responses", "chat_completions"],
        timeout_seconds: float,
        api_key: str | None,
        clear_api_key: bool,
    ) -> dict[str, object]:
        with self._lock:
            current = self._effective_values()
            if enabled:
                retained_key = "" if clear_api_key else current.get("HAWKEYE_LLM_API_KEY", "")
                next_key = api_key.strip() if api_key and api_key.strip() else retained_key
                if "\r" in next_key or "\n" in next_key:
                    raise ValueError("HAWKEYE_LLM_API_KEY cannot contain a line break")
                config = LlmConfig(
                    base_url=base_url,
                    model=model,
                    api_style=api_style,
                    timeout_seconds=timeout_seconds,
                    api_key=next_key or None,
                )
                managed = {
                    "HAWKEYE_LLM_ENABLED": "1",
                    "HAWKEYE_LLM_BASE_URL": config.base_url,
                    "HAWKEYE_LLM_MODEL": config.model,
                    "HAWKEYE_LLM_API_STYLE": config.api_style,
                    "HAWKEYE_LLM_TIMEOUT_SECONDS": str(config.timeout_seconds)
                    .rstrip("0")
                    .rstrip("."),
                }
                if next_key:
                    managed["HAWKEYE_LLM_API_KEY"] = next_key
                for key, value in managed.items():
                    if "\r" in value or "\n" in value:
                        raise ValueError(f"{key} cannot contain a line break")
            else:
                managed = {
                    key: value
                    for key, value in current.items()
                    if key in _MANAGED_KEYS and key != "HAWKEYE_LLM_ENABLED"
                }
                managed["HAWKEYE_LLM_ENABLED"] = "0"

            preserved = {
                key: value
                for key, value in _read_settings(self.path).items()
                if key not in _MANAGED_KEYS
            }
            self._write({**preserved, **managed})
            for key in _MANAGED_KEYS:
                if key in managed:
                    os.environ[key] = managed[key]
                else:
                    os.environ.pop(key, None)
            return self.view()

    def _effective_values(self) -> dict[str, str]:
        values = _read_settings(self.path)
        for key in _MANAGED_KEYS:
            environment_value = os.environ.get(key)
            if environment_value is not None:
                values[key] = environment_value
        return values

    def _write(self, values: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        lines = [
            "# HAWK-EYE local desktop settings. Never share or commit this file.",
            "# Provider changes apply to new investigations in this running app.",
            "",
        ]
        lines.extend(f"{key}={value}" for key, value in sorted(values.items()))
        temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
        temporary.replace(self.path)


def _read_settings(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key.startswith("HAWKEYE_") or not key.replace("_", "").isalnum():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


def _safe_timeout(value: str | None) -> float:
    try:
        timeout = float(value or "15")
    except ValueError:
        return 15.0
    return timeout if 0 < timeout <= 60 else 15.0
