"""Local MVP API workflow and same-origin mutation controls."""

from __future__ import annotations

from pathlib import Path

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
            json={"seed_url": f"{fixture_server_url}normal-content.html"},
        )

        assert created.status_code == 200
        payload = created.json()
        assert payload["capture_adequacy"] == "adequate"
        assert payload["access_outcome"] == "content"
        assert payload["public_status"] == "captured"
        assert payload["pages"][0]["readiness_evidence_id"]
        assert payload["source_kind"] == "live_capture"
        assert payload["workspace_id"].startswith("run-live-")
        run = client.get(f"/api/mvp/runs/{payload['workspace_id']}").json()
        assert run["source_case_id"] == payload["case_id"]
        assert run["source_case"]["case_id"] == payload["case_id"]
        assert run["agent_mode"] in {"codex", "deterministic_fallback"}
        assert {item["kind"] for item in run["events"]} >= {
            "run.started",
            "artifact.captured",
            "agent.objective.created",
        }
        assert client.get("/api/cases").json()["cases"][0]["case_id"] == payload["case_id"]
