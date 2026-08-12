from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hawkeye import desktop
from hawkeye.desktop_settings import DesktopSettingsStore
from hawkeye.review_app.app import create_app

_LLM_ENV_KEYS = (
    "HAWKEYE_LLM_ENABLED",
    "HAWKEYE_LLM_BASE_URL",
    "HAWKEYE_LLM_API_KEY",
    "HAWKEYE_LLM_MODEL",
    "HAWKEYE_LLM_API_STYLE",
    "HAWKEYE_LLM_TIMEOUT_SECONDS",
)


@pytest.fixture(autouse=True)
def restore_llm_environment() -> object:
    before = {key: desktop.os.environ.get(key) for key in _LLM_ENV_KEYS}
    yield
    for key, value in before.items():
        if value is None:
            desktop.os.environ.pop(key, None)
        else:
            desktop.os.environ[key] = value


def test_desktop_paths_use_explicit_data_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HAWKEYE_DATA_DIR", str(tmp_path / "portable-data"))

    paths = desktop.DesktopPaths.resolve()
    paths.create()

    assert paths.root == (tmp_path / "portable-data").resolve()
    assert paths.cases.is_dir()
    assert paths.workspace.is_dir()
    assert paths.comparisons.is_dir()
    assert paths.logs.is_dir()


def test_desktop_settings_are_bounded_and_do_not_override_process_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HAWKEYE_LLM_API_KEY", raising=False)
    settings = tmp_path / "settings.env"
    settings.write_text(
        "HAWKEYE_LLM_MODEL='configured-model'\n"
        "HAWKEYE_LLM_API_KEY=desktop-secret\n"
        "PATH=attacker-controlled\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HAWKEYE_LLM_MODEL", "operator-model")
    original_path = desktop.os.environ.get("PATH")

    desktop._load_settings(settings)

    assert desktop.os.environ["HAWKEYE_LLM_MODEL"] == "operator-model"
    assert desktop.os.environ["HAWKEYE_LLM_API_KEY"] == "desktop-secret"
    assert desktop.os.environ.get("PATH") == original_path


def test_existing_runtime_requires_expected_loopback_health(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "runtime.json"
    runtime.write_text(json.dumps({"url": "http://127.0.0.1:54321/", "pid": 42}), encoding="utf-8")
    monkeypatch.setattr(desktop, "_is_hawkeye_health", lambda _: True)

    assert desktop._existing_runtime_url(runtime) == "http://127.0.0.1:54321/"


@pytest.mark.parametrize("value", ["not-a-number", "-1", "65536"])
def test_invalid_desktop_port_fails_closed(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAWKEYE_PORT", value)
    with pytest.raises(ValueError, match="port|integer"):
        desktop._requested_port(None)


def test_default_desktop_port_falls_back_to_ephemeral_when_occupied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HAWKEYE_PORT", raising=False)
    calls: list[int] = []
    fallback = object()

    def bind(port: int) -> object:
        calls.append(port)
        if port == desktop._DEFAULT_PORT:
            raise OSError("occupied")
        return fallback

    monkeypatch.setattr(desktop, "_bind_loopback", bind)
    assert desktop._bind_desktop_loopback(None) is fallback
    assert calls == [desktop._DEFAULT_PORT, 0]


def test_explicit_desktop_port_never_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        desktop,
        "_bind_loopback",
        lambda _: (_ for _ in ()).throw(OSError("occupied")),
    )
    with pytest.raises(OSError, match="occupied"):
        desktop._bind_desktop_loopback(8760)


def test_desktop_settings_api_persists_provider_without_returning_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in _LLM_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    cases = tmp_path / "cases"
    cases.mkdir()
    store = DesktopSettingsStore(tmp_path / "profile" / "settings.env")
    app = create_app(
        cases,
        workspace_root=tmp_path / "workspace",
        desktop_settings=store,
    )

    with TestClient(app, base_url="http://127.0.0.1:8760") as client:
        initial = client.get("/api/settings")
        assert initial.status_code == 200
        assert initial.json()["api_key_configured"] is False
        assert initial.json()["capability"]["state"] == "fallback_only"

        secret = "sk-test-desktop-secret"
        saved = client.put(
            "/api/settings",
            headers={"Origin": "http://127.0.0.1:8760"},
            json={
                "enabled": True,
                "base_url": "https://openrouter.ai/api/v1",
                "model": "openai/test-model",
                "api_style": "chat_completions",
                "timeout_seconds": 30,
                "api_key": secret,
                "clear_api_key": False,
            },
        )
        assert saved.status_code == 200
        assert saved.json()["api_key_configured"] is True
        assert saved.json()["capability"]["state"] == "model_configured_unverified"
        assert secret not in saved.text

        reread = client.get("/api/settings")
        assert reread.status_code == 200
        assert secret not in reread.text

        rejected = client.put(
            "/api/settings",
            headers={"Origin": "https://attacker.invalid"},
            json={"enabled": False},
        )
        assert rejected.status_code == 403

        invalid = client.put(
            "/api/settings",
            headers={"Origin": "http://127.0.0.1:8760"},
            json={
                "enabled": True,
                "base_url": "http://provider.example/api/v1",
                "model": "unsafe-model",
                "api_style": "auto",
                "timeout_seconds": 15,
            },
        )
        assert invalid.status_code == 422
        assert "HTTPS" in invalid.json()["detail"]

        oversized_secret = "sk-" + ("x" * 4096)
        oversized = client.put(
            "/api/settings",
            headers={"Origin": "http://127.0.0.1:8760"},
            json={
                "enabled": True,
                "base_url": "https://openrouter.ai/api/v1",
                "model": "openai/test-model",
                "api_style": "chat_completions",
                "timeout_seconds": 30,
                "api_key": oversized_secret,
            },
        )
        assert oversized.status_code == 422
        assert oversized_secret not in oversized.text

        disabled = client.put(
            "/api/settings",
            headers={"Origin": "http://127.0.0.1:8760"},
            json={"enabled": False},
        )
        assert disabled.status_code == 200
        assert disabled.json()["enabled"] is False
        assert disabled.json()["api_key_configured"] is True
        assert disabled.json()["capability"]["state"] == "fallback_only"

    persisted = store.path.read_text(encoding="utf-8")
    assert "HAWKEYE_LLM_API_KEY=" + secret in persisted
    assert "openai/test-model" in persisted
    assert "HAWKEYE_LLM_ENABLED=0" in persisted
