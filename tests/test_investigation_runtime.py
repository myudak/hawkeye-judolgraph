"""G7/G8 recollection, append-only reviews, events, and graph replay tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hawkeye.investigation import InvestigationStore, reduce_events, run_fixture_investigation


def test_synthetic_page_a_to_page_b_flow_requires_recollection_and_review(tmp_path: Path) -> None:
    result = run_fixture_investigation("redirect-new-tab", tmp_path / "run")
    root = Path(result.directory)
    assert result.agent_mode == "deterministic_fallback"
    assert result.lead_status == "recollected"
    assert result.assertion_id == "assertion-06"
    assert (root / "artifacts/page-a.json").is_file()
    assert (root / "artifacts/page-b.json").is_file()
    store = InvestigationStore(result.database_path)
    assertion = store.assertion("assertion-06")
    assert assertion.assertion_type == "shares_redirect_target_with"
    assert assertion.supporting_observation_ids == ["obs-page-a-interaction-001", "obs-page-b-001"]
    assert assertion.source_artifact_ids == ["artifact-page-a", "artifact-page-b"]
    assert store.current_assertion_status(assertion.assertion_id) == "needs_review"
    kinds = [event.kind for event in store.events(result.run_id)]
    assert kinds.index("search.lead.discovered") < kinds.index("candidate_page.collected")
    assert kinds.index("candidate_page.collected") < kinds.index("assertion.proposed")
    assert kinds.index("assertion.proposed") < kinds.index("review.required")


def test_real_world_candidate_stops_for_explicit_recollection_approval(tmp_path: Path) -> None:
    result = run_fixture_investigation(
        "redirect-new-tab", tmp_path / "real-run", collection_mode="real_world"
    )
    assert result.lead_status == "waiting_for_approval"
    assert result.assertion_id is None
    assert not (Path(result.directory) / "artifacts/page-b.json").exists()
    kinds = [event.kind for event in InvestigationStore(result.database_path).events(result.run_id)]
    assert "candidate_page.approval_required" in kinds
    assert "candidate_page.collected" not in kinds


def test_unsafe_fixture_controls_persist_blocked_preflight_without_execution(
    tmp_path: Path,
) -> None:
    result = run_fixture_investigation("login-register-distractors", tmp_path / "blocked-run")
    events = InvestigationStore(result.database_path).events(result.run_id)
    blocked = [item for item in events if item.kind == "tool.blocked"]
    assert len(blocked) == 2
    assert {item.payload["element_id"] for item in blocked} == {"login", "register"}
    assert all(item.payload["policy_preflight"] is True for item in blocked)
    assert all(item.payload["executed"] is False for item in blocked)
    for event in blocked:
        requested = next(item for item in events if item.event_id == event.causation_event_id)
        assert requested.kind == "tool.requested"
        assert requested.payload["executed"] is False


def test_review_history_is_append_only_and_current_status_is_derived(tmp_path: Path) -> None:
    result = run_fixture_investigation("redirect-new-tab", tmp_path / "run")
    store = InvestigationStore(result.database_path)
    first = store.append_review(
        "assertion-06",
        outcome="needs_more_evidence",
        reviewer_label="fixture-reviewer",
        reason="Request a second direct observation.",
    )
    second = store.append_review(
        "assertion-06",
        outcome="verified",
        reviewer_label="fixture-reviewer",
        reason="Selected evidence supports only the stated redirect-target relationship.",
    )
    assert (first.previous_version, first.new_version) == (0, 1)
    assert (second.previous_version, second.new_version) == (1, 2)
    assert [item.outcome for item in store.review_history("assertion-06")] == [
        "needs_more_evidence",
        "verified",
    ]
    assert store.current_assertion_status("assertion-06") == "verified"
    with (
        sqlite3.connect(store.path) as connection,
        pytest.raises(sqlite3.IntegrityError, match="append-only"),
    ):
        connection.execute("UPDATE reviews SET reason = 'changed'")


def test_event_sequence_idempotence_and_graph_replay_consistency(tmp_path: Path) -> None:
    result = run_fixture_investigation("redirect-new-tab", tmp_path / "run")
    store = InvestigationStore(result.database_path)
    events = store.events(result.run_id)
    assert [item.sequence for item in events] == list(range(1, len(events) + 1))
    duplicate = store.append_event(
        case_id=result.case_id,
        run_id=result.run_id,
        kind=events[0].kind,
        payload=events[0].payload,
        event_id=events[0].event_id,
    )
    assert duplicate == events[0]
    first = reduce_events(events)
    replayed = reduce_events([*events, *events])
    assert replayed == first
    proposed_edge = next(edge for edge in first.edges if edge.id == "assertion:assertion-06")
    assert proposed_edge.appearance == "dashed"
    assert proposed_edge.source == "page:a"
    assert proposed_edge.target == "page:b"
    store.append_review(
        "assertion-06",
        outcome="verified",
        reviewer_label="fixture-reviewer",
        reason="Evidence supports the stated relation; no ownership conclusion.",
    )
    verified = reduce_events(store.events(result.run_id))
    assertion_edge = next(edge for edge in verified.edges if edge.id == "assertion:assertion-06")
    assert assertion_edge.appearance == "solid_emphasized"
    assert {item.animation for item in verified.animations} >= {
        "spawn-node",
        "draw-edge",
        "pulse-node",
    }
