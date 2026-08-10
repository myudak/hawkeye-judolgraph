"""Local MVP API workflow and same-origin mutation controls."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hawkeye.collector.safety import SafetyPolicy
from hawkeye.review_app.app import create_app


def _client(tmp_path: Path) -> TestClient:
    cases = tmp_path / "cases"
    cases.mkdir()
    return TestClient(
        create_app(cases, workspace_root=tmp_path / "workspace"),
        base_url="http://127.0.0.1",
    )


def test_full_synthetic_ui_api_flow_creates_graph_and_append_only_review(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        scenarios = client.get("/api/mvp/scenarios")
        assert scenarios.status_code == 200
        assert len(scenarios.json()["scenarios"]) == 10
        created = client.post(
            "/api/mvp/runs",
            json={"scenario_id": "redirect-new-tab", "collection_mode": "synthetic_fixture"},
        )
        assert created.status_code == 200
        workspace_id = created.json()["workspace_id"]
        details = client.get(f"/api/mvp/runs/{workspace_id}")
        assert details.status_code == 200
        payload = details.json()
        assert payload["agent_mode"] == "deterministic_fallback"
        assert payload["lead_status"] == "recollected"
        assert payload["current_assertion_status"] == "needs_review"
        assert payload["graph"]["nodes"]
        assert payload["graph"]["edges"]
        assert payload["graph"]["timeline"]
        artifact_event = next(
            event for event in payload["events"] if event["kind"] == "artifact.captured"
        )
        assert artifact_event["payload"]["path"] == "artifacts/page-a.json"
        review = client.post(
            f"/api/mvp/runs/{workspace_id}/reviews",
            json={
                "assertion_id": "assertion-06",
                "outcome": "verified",
                "reviewer_label": "UI fixture reviewer",
                "reason": "Selected evidence supports only the stated redirect-target relation.",
            },
        )
        assert review.status_code == 200
        reviewed = client.get(f"/api/mvp/runs/{workspace_id}").json()
        assert reviewed["current_assertion_status"] == "verified"
        assert reviewed["reviews"][0]["previous_version"] == 0
        assert reviewed["reviews"][0]["new_version"] == 1
        edge = next(
            item for item in reviewed["graph"]["edges"] if item["id"] == "assertion:assertion-06"
        )
        assert edge["appearance"] == "solid_emphasized"
        markdown = client.get(f"/api/mvp/runs/{workspace_id}/export.md")
        structured = client.get(f"/api/mvp/runs/{workspace_id}/export.json")
        archive = client.get(f"/api/mvp/runs/{workspace_id}/export.zip")
        assert markdown.status_code == 200
        assert b"Candidate assertions" in markdown.content
        assert structured.status_code == 200
        assert structured.json()["workspace_id"] == workspace_id
        assert archive.status_code == 200
        assert archive.content.startswith(b"PK")


def test_approval_gated_mode_recollects_page_b_only_after_explicit_approval(
    tmp_path: Path,
) -> None:
    with _client(tmp_path) as client:
        created = client.post(
            "/api/mvp/runs",
            json={"scenario_id": "redirect-new-tab", "collection_mode": "real_world"},
        ).json()
        workspace_id = created["workspace_id"]
        details = client.get(f"/api/mvp/runs/{workspace_id}").json()
        assert details["lead_status"] == "waiting_for_approval"
        approval = client.post(f"/api/mvp/runs/{workspace_id}/approve", json={})
        assert approval.status_code == 200
        approved = client.get(f"/api/mvp/runs/{workspace_id}").json()
        assert approved["lead_status"] == "recollected"
        assert approved["assertion"]["assertion_id"] == "assertion-06"
        kinds = [event["kind"] for event in approved["events"]]
        assert kinds.index("candidate_page.approved") < kinds.index("candidate_page.collected")


def test_cross_origin_mutation_and_artifact_traversal_are_blocked(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        blocked = client.post(
            "/api/mvp/runs",
            json={"scenario_id": "redirect-new-tab"},
            headers={"Origin": "https://attacker.invalid"},
        )
        assert blocked.status_code == 403
        created = client.post("/api/mvp/runs", json={"scenario_id": "redirect-new-tab"}).json()
        workspace_id = created["workspace_id"]
        traversal = client.get(f"/api/mvp/runs/{workspace_id}/artifacts/..%2Fpage-a.json")
        assert traversal.status_code in {400, 404}


def test_exact_public_demo_origin_allows_public_and_local_browser_mutations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HAWKEYE_PUBLIC_DEMO_ORIGIN", "https://hawkeye.myudak.com")
    cases = tmp_path / "cases"
    cases.mkdir()
    app = create_app(cases, workspace_root=tmp_path / "workspace")

    with TestClient(app, base_url="http://hawkeye.myudak.com") as public_client:
        allowed = public_client.post(
            "/api/mvp/runs",
            json={"scenario_id": "redirect-new-tab"},
            headers={"Origin": "https://hawkeye.myudak.com"},
        )
        assert allowed.status_code == 200
        assert "access-control-allow-origin" not in allowed.headers

        for origin in (
            None,
            "null",
            "http://hawkeye.myudak.com",
            "https://hawkeye.myudak.com:444",
            "https://sub.hawkeye.myudak.com",
            "https://attacker.invalid",
        ):
            headers = {} if origin is None else {"Origin": origin}
            blocked = public_client.post(
                "/api/mvp/runs",
                json={"scenario_id": "redirect-new-tab"},
                headers=headers,
            )
            assert blocked.status_code == 403
            assert blocked.json() == {"detail": "cross_origin_mutation_blocked"}

    with TestClient(app, base_url="http://127.0.0.1:8760") as local_client:
        local = local_client.post(
            "/api/mvp/runs",
            json={"scenario_id": "redirect-new-tab"},
            headers={"Origin": "http://127.0.0.1:8760"},
        )
        assert local.status_code == 200


@pytest.mark.parametrize(
    "origin",
    [
        "http://hawkeye.myudak.com",
        "https://*.myudak.com",
        "https://user:password@hawkeye.myudak.com",
        "https://hawkeye.myudak.com:444",
        "https://hawkeye.myudak.com.",
        "https://hawkeye.myudak.com/path",
        "https://hawkeye.myudak.com?query=yes",
        "https://hawkeye.myudak.com#fragment",
    ],
)
def test_invalid_public_demo_origin_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, origin: str
) -> None:
    monkeypatch.setenv("HAWKEYE_PUBLIC_DEMO_ORIGIN", origin)
    cases = tmp_path / "cases"
    cases.mkdir()

    with pytest.raises(ValueError, match="HAWKEYE_PUBLIC_DEMO_ORIGIN"):
        create_app(cases, workspace_root=tmp_path / "workspace")


def test_public_demo_ignores_forwarded_host_and_rejects_duplicate_origins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HAWKEYE_PUBLIC_DEMO_ORIGIN", "https://hawkeye.myudak.com")
    cases = tmp_path / "cases"
    cases.mkdir()
    app = create_app(cases, workspace_root=tmp_path / "workspace")

    with TestClient(app, base_url="http://hawkeye.myudak.com") as client:
        forwarded = client.post(
            "/api/mvp/runs",
            json={"scenario_id": "redirect-new-tab"},
            headers={
                "Host": "attacker.invalid",
                "Origin": "https://hawkeye.myudak.com",
                "Forwarded": "host=hawkeye.myudak.com;proto=https",
                "X-Forwarded-Host": "hawkeye.myudak.com",
            },
        )
        duplicate = client.post(
            "/api/mvp/runs",
            json={"scenario_id": "redirect-new-tab"},
            headers=[
                ("Origin", "https://hawkeye.myudak.com"),
                ("Origin", "https://hawkeye.myudak.com"),
            ],
        )

        assert forwarded.status_code == 400
        assert duplicate.status_code == 403


def test_ui_can_create_one_bounded_seed_capture(tmp_path: Path, fixture_server_url: str) -> None:
    cases = tmp_path / "cases"
    cases.mkdir()
    app = create_app(
        cases,
        workspace_root=tmp_path / "workspace",
        collection_safety_policy=SafetyPolicy(allow_loopback_for_testing=True),
    )
    with TestClient(app, base_url="http://127.0.0.1") as client:
        created = client.post(
            "/api/cases",
            json={
                "seed_url": f"{fixture_server_url}normal-content.html",
                "investigation_name": "Capture-only fixture",
                "investigation_mode": "capture_only",
            },
        )

        assert created.status_code == 200
        payload = created.json()
        assert payload["capture_adequacy"] == "adequate"
        assert payload["access_outcome"] == "content"
        assert payload["public_status"] == "captured"
        assert payload["pages"][0]["readiness_evidence_id"]
        assert payload["pages"][0]["ocr_metadata_evidence_id"]
        assert payload["source_kind"] == "live_capture"
        assert payload["workspace_id"].startswith("run-live-")
        run = client.get(f"/api/mvp/runs/{payload['workspace_id']}").json()
        assert run["source_case_id"] == payload["case_id"]
        assert run["source_case"]["case_id"] == payload["case_id"]
        assert run["agent_mode"] == "not_requested"
        assert run["agent_stop_reason"] == "capture_only_mode"
        assert run["investigation_name"] == "Capture-only fixture"
        assert {item["kind"] for item in run["events"]} >= {
            "run.started",
            "artifact.captured",
            "agent.objective.created",
        }
        assert client.get("/api/cases").json()["cases"][0]["case_id"] == payload["case_id"]


def test_progressive_ui_job_reports_real_capture_stages(
    tmp_path: Path,
    fixture_server_url: str,
) -> None:
    cases = tmp_path / "cases"
    cases.mkdir()
    app = create_app(
        cases,
        workspace_root=tmp_path / "workspace",
        collection_safety_policy=SafetyPolicy(allow_loopback_for_testing=True),
    )
    with TestClient(app, base_url="http://127.0.0.1") as client:
        created = client.post(
            "/api/investigation-jobs",
            json={
                "seed_url": f"{fixture_server_url}normal-content.html",
                "investigation_name": "Progress fixture",
                "investigation_mode": "capture_only",
            },
        )
        assert created.status_code == 202
        job_id = created.json()["job_id"]
        deadline = time.monotonic() + 45
        status = created.json()
        while status["status"] in {"queued", "running"} and time.monotonic() < deadline:
            time.sleep(0.1)
            status = client.get(f"/api/investigation-jobs/{job_id}").json()

        assert status["status"] == "completed", status
        stages = {item["stage"] for item in status["history"]}
        assert {
            "launching_browser",
            "capturing_page",
            "preserving_artifacts",
            "page_preview_ready",
            "evidence_verified",
            "extracting_evidence",
            "classifying_indicators",
            "building_graph",
            "completed",
        } <= stages
        visual = status["visual_state"]
        assert visual["revision"] >= 1
        assert visual["latest_preview"]["kind"] == "canonical"
        assert visual["latest_preview"]["verification"] == "verified"
        assert "case_id" not in visual["latest_preview"]
        preview = client.get(
            f"/api/investigation-jobs/{job_id}/preview",
            params={"revision": visual["latest_preview"]["revision"]},
        )
        assert preview.status_code == 200
        assert preview.headers["content-type"] == "image/png"
        assert preview.headers["x-hawkeye-preview-state"] == "verified"
        assert preview.content.startswith(b"\x89PNG\r\n\x1a\n")
        thumbnail = client.get(
            f"/api/investigation-jobs/{job_id}/preview",
            params={
                "revision": visual["latest_preview"]["revision"],
                "thumbnail": True,
            },
        )
        assert thumbnail.status_code == 200
        assert thumbnail.headers["content-type"] == "image/png"
        assert len(thumbnail.content) < len(preview.content)
        assert status["result"]["gambling_indicators"]["indicator_count"] >= 0
        assert client.get("/api/investigation-jobs/active").json() == {"job": None}
