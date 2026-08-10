"""Single-operator HTTP Basic authentication boundary."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hawkeye.review_app.app import create_app


def _authorization(username: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def _configure(monkeypatch: pytest.MonkeyPatch) -> tuple[str, str]:
    username = "local-investigator"
    password = "correct horse battery staple"
    monkeypatch.setenv("HAWKEYE_AUTH_USERNAME", username)
    monkeypatch.setenv("HAWKEYE_AUTH_PASSWORD", password)
    return username, password


def test_configured_auth_protects_ui_and_api_but_not_health(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    username, password = _configure(monkeypatch)
    cases = tmp_path / "cases"
    cases.mkdir()
    client = TestClient(create_app(cases), base_url="http://127.0.0.1")

    health = client.get("/health")
    unauthenticated = client.get("/api/cases")
    incorrect = client.get("/api/cases", headers=_authorization(username, "incorrect"))
    authenticated = client.get("/api/cases", headers=_authorization(username, password))

    assert health.status_code == 200
    assert unauthenticated.status_code == 401
    assert unauthenticated.json() == {"error": "authentication_required"}
    assert unauthenticated.headers["www-authenticate"] == ('Basic realm="HAWKEYE", charset="UTF-8"')
    assert "default-src 'self'" in unauthenticated.headers["content-security-policy"]
    assert password not in unauthenticated.text
    assert incorrect.status_code == 401
    assert authenticated.status_code == 200
    assert authenticated.json() == {"cases": []}


def test_host_validation_precedes_authentication_challenge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    username, password = _configure(monkeypatch)
    cases = tmp_path / "cases"
    cases.mkdir()
    client = TestClient(create_app(cases), base_url="http://127.0.0.1")

    blocked = client.get(
        "/api/cases",
        headers={"host": "evil.example", **_authorization(username, password)},
    )

    assert blocked.status_code == 400


@pytest.mark.parametrize(
    ("username", "password"),
    [("configured", ""), ("", "configured")],
)
def test_partial_auth_configuration_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    username: str,
    password: str,
) -> None:
    monkeypatch.setenv("HAWKEYE_AUTH_USERNAME", username)
    monkeypatch.setenv("HAWKEYE_AUTH_PASSWORD", password)
    cases = tmp_path / "cases"
    cases.mkdir()

    with pytest.raises(ValueError, match="must both be configured"):
        create_app(cases)


def test_auth_remains_disabled_when_both_values_are_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HAWKEYE_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("HAWKEYE_AUTH_PASSWORD", raising=False)
    cases = tmp_path / "cases"
    cases.mkdir()
    client = TestClient(create_app(cases), base_url="http://127.0.0.1")

    assert client.get("/api/cases").status_code == 200


@pytest.mark.parametrize(
    "authorization",
    ["Basic !!!", "Bearer token", "Basic", "Basic Zm9v"],
)
def test_malformed_authorization_is_rejected_without_error_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authorization: str,
) -> None:
    _configure(monkeypatch)
    cases = tmp_path / "cases"
    cases.mkdir()
    client = TestClient(create_app(cases), base_url="http://127.0.0.1")

    response = client.get("/api/cases", headers={"Authorization": authorization})

    assert response.status_code == 401
    assert response.json() == {"error": "authentication_required"}
