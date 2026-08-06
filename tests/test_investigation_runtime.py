"""G7/G8 recollection, append-only reviews, events, and graph replay tests."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from hawkeye.collector.safety import SafetyPolicy
from hawkeye.investigation import (
    InvestigationStore,
    reduce_events,
    run_fixture_investigation,
    run_live_investigation,
)
from hawkeye.models import CaseRecord, CrawlFrontierRecord, CrawlPageRecord, InvestigationResult


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
    assert proposed_edge.source == "seed:fixture-redirect-new-tab"
    target = next(node for node in first.nodes if node.id == proposed_edge.target)
    assert target.kind == "collected_page"
    assert target.label == "https://candidate-f.example.invalid/final"
    assert sum(node.label == "https://scenario-6.example.invalid/" for node in first.nodes) == 1
    assert (
        sum(node.label == "https://candidate-f.example.invalid/final" for node in first.nodes) == 1
    )
    assert all(edge.source != edge.target for edge in first.edges)
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


def test_live_graph_collapses_root_capture_and_projects_meaningful_relation(
    tmp_path: Path,
) -> None:
    store = InvestigationStore(tmp_path / "events.sqlite3")
    started = store.append_event(
        case_id="case-live",
        run_id="run-live",
        kind="run.started",
        payload={"seed_url": "https://source.example/"},
    )
    captured = store.append_event(
        case_id="case-live",
        run_id="run-live",
        kind="artifact.captured",
        payload={
            "node_id": "page:page-001",
            "root": True,
            "label": "https://source.example/",
        },
        causation_event_id=started.event_id,
    )
    observation = store.append_event(
        case_id="case-live",
        run_id="run-live",
        kind="observation.created",
        payload={
            "observation_id": "obs-link",
            "node_id": "observable:target",
            "source_node_id": "page:page-001",
            "observation_type": "public_outgoing_link",
            "normalized_value": "https://target.example/",
            "matched_case_id": "case-target",
        },
        causation_event_id=captured.event_id,
    )
    store.append_event(
        case_id="case-live",
        run_id="run-live",
        kind="entity.matched",
        payload={"observation_id": "obs-link", "target_case_id": "case-target"},
        causation_event_id=observation.event_id,
    )

    graph = reduce_events(store.events("run-live"))

    assert {node.id for node in graph.nodes} == {
        "seed:case-live",
        "external_destination:target.example",
    }
    destination = next(
        node for node in graph.nodes if node.id == "external_destination:target.example"
    )
    assert destination.kind == "external_destination"
    assert destination.status == "collected"
    assert len(graph.edges) == 1
    assert graph.edges[0].source == "seed:case-live"
    assert graph.edges[0].relation == "publicly_links_to"


def test_graph_groups_domains_and_never_labels_claim_keywords_as_contacts(
    tmp_path: Path,
) -> None:
    store = InvestigationStore(tmp_path / "taxonomy.sqlite3")
    started = store.append_event(
        case_id="case-taxonomy",
        run_id="run-taxonomy",
        kind="run.started",
        payload={"seed_url": "https://888.com/"},
    )
    captured = store.append_event(
        case_id="case-taxonomy",
        run_id="run-taxonomy",
        kind="artifact.captured",
        payload={"node_id": "page:root", "root": True, "label": "https://888.com/"},
        causation_event_id=started.event_id,
    )
    observations = [
        ("link-one", "public_outgoing_link", "https://www.888casino.com/slots"),
        ("link-two", "public_outgoing_link", "https://888casino.com/blackjack"),
        ("same-host", "public_outgoing_link", "https://888.com/about-us"),
        ("deposit", "public_payment_method", "deposit"),
        ("withdrawal", "public_payment_method", "withdrawal"),
        ("bonus", "public_offer_claim", "bonus"),
        ("tracking", "public_tracking_identifier", "utm_source=cmp"),
        ("phone", "public_phone_number", "+639543355092"),
        ("telegram", "public_telegram_contact", "+639543355092"),
    ]
    for observation_id, observation_type, value in observations:
        store.append_event(
            case_id="case-taxonomy",
            run_id="run-taxonomy",
            kind="observation.created",
            payload={
                "observation_id": observation_id,
                "node_id": f"observable:{observation_id}",
                "source_node_id": "page:root",
                "observation_type": observation_type,
                "normalized_value": value,
            },
            causation_event_id=captured.event_id,
        )

    graph = reduce_events(store.events("run-taxonomy"))

    destination = next(node for node in graph.nodes if node.kind == "external_destination")
    assert destination.label == "888casino.com"
    assert all(
        node.label != "888.com" for node in graph.nodes if node.kind == "external_destination"
    )
    assert destination.attributes["observed_urls"] == [
        "https://888casino.com/blackjack",
        "https://www.888casino.com/slots",
    ]
    payment = next(
        node
        for node in graph.nodes
        if node.kind == "public_claim" and node.attributes["claim_category"] == "payment_indicators"
    )
    assert payment.attributes["values"] == ["deposit", "withdrawal"]
    contacts = [node for node in graph.nodes if node.kind == "public_contact"]
    assert [node.label for node in contacts] == ["+639543355092", "+639543355092"]
    assert {node.attributes["observation_type"] for node in contacts} == {
        "public_phone_number",
        "public_telegram_contact",
    }
    assert all(node.label not in {"bonus", "deposit", "withdrawal"} for node in contacts)
    destination_edges = [edge for edge in graph.edges if edge.target == destination.id]
    assert len(destination_edges) == 1
    assert len(destination_edges[0].supporting_observation_ids) == 2


def test_candidate_priority_prefers_core_888_product_domains() -> None:
    from hawkeye.investigation.live_runtime import _candidate_priority

    assert _candidate_priority("888casino.com", "888.com", "888") == 0
    assert _candidate_priority("888poker.com", "888.com", "888") == 0
    assert _candidate_priority("888sport.com", "888.com", "888") == 0
    assert _candidate_priority("888responsible.com", "888.com", "888") == 1
    assert _candidate_priority("affiliates.888.com", "888.com", "888") == 3


def test_contact_route_fallback_is_same_origin_and_contact_only() -> None:
    from hawkeye.investigation.live_runtime import (
        _contact_route_fallback,
        _reference_label_matches,
    )

    assert (
        _contact_route_fallback("https://qq101xfw.com/start", "Hubungi Kami")
        == "https://qq101xfw.com/Contact"
    )
    assert (
        _contact_route_fallback("https://example.test/start", "Support")
        == "https://example.test/Help"
    )
    assert _contact_route_fallback("https://example.test/start", "Promotion") is None
    assert _reference_label_matches("Contact Us", "Hubungi Kami") is True
    assert _reference_label_matches("Promotion", "Hubungi Kami") is False


def test_live_contact_action_persists_route_screenshot_and_contact_observations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hawkeye.investigation.live_runtime as live_runtime

    now = datetime.now(UTC)
    package = tmp_path / "contact-case"
    pages = package / "pages"
    pages.mkdir(parents=True)
    (pages / "page-001.html").write_text(
        "<html><body><a class='contact'>Contact Us</a><a>Promotion</a></body></html>",
        encoding="utf-8",
    )
    result = InvestigationResult(
        case_directory=str(package),
        case=CaseRecord(
            case_id="case-contact",
            seed_url="https://contact.example/",
            final_url="https://contact.example/",
            status="completed",
            started_at=now,
            completed_at=now,
            page_count=1,
        ),
        pages=[
            CrawlPageRecord(
                id="page-001",
                url="https://contact.example/",
                normalized_url="https://contact.example/",
                final_url="https://contact.example/",
                depth=0,
                state="completed",
                html_evidence_id="evidence-page-001",
                screenshot_evidence_id="evidence-screenshot-001",
            )
        ],
    )
    contact_html = """
    <html><body>
      <h1>Hubungi Kami</h1>
      <section>Nomor Kontak +639543355092</section>
      <section>Whats App +639543355092</section>
      <section>Telegram +639157800101</section>
    </body></html>
    """

    def execute_contact(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "status": "completed",
            "reason": "validated_public_reveal",
            "url": "https://contact.example/Contact",
            "state_artifact": "interaction-001.json",
            "screenshot_artifact": "interaction-001.png",
            "html_artifact": "interaction-001.html",
            "visible_text_artifact": "interaction-001.txt",
            "request_count": 1,
            "blocked_request_count": 0,
            "executed": True,
            "_html": contact_html,
        }

    monkeypatch.setattr(live_runtime, "_execute_live_interaction", execute_contact)
    output = tmp_path / "contact-run"
    summary = run_live_investigation(
        result,
        output,
        investigator=None,
        known_cases=[],
        safety_policy=SafetyPolicy(),
    )
    store = InvestigationStore(output / "investigation.sqlite3")
    events = store.events(str(summary["run_id"]))
    requested = next(
        event
        for event in events
        if event.kind == "tool.requested" and event.payload.get("executed") is True
    )
    assert requested.payload["element_reference"]["accessible_name"] == "Contact Us"
    contact_observations = [
        event.payload
        for event in events
        if event.kind == "observation.created"
        and event.payload.get("source_node_id", "").startswith("route:")
    ]
    assert {item["observation_type"] for item in contact_observations} >= {
        "public_phone_number",
        "public_whatsapp_link",
        "public_telegram_contact",
    }
    graph = reduce_events(events)
    route = next(node for node in graph.nodes if node.label.endswith("/Contact"))
    assert route.attributes["screenshot_artifact"] == "interaction-001.png"
    assert any(
        edge.target == route.id and edge.relation == "opened_safe_public_route"
        for edge in graph.edges
    )


def test_direct_frontier_anchor_auto_matches_an_already_collected_related_case(
    tmp_path: Path,
) -> None:
    now = datetime.now(UTC)
    package = tmp_path / "case-package"
    package.mkdir()
    result = InvestigationResult(
        case_directory=str(package),
        case=CaseRecord(
            case_id="case-888",
            seed_url="https://888.com/",
            final_url="https://888.com/",
            status="completed",
            started_at=now,
            completed_at=now,
            page_count=1,
        ),
        pages=[
            CrawlPageRecord(
                id="page-001",
                url="https://888.com/",
                normalized_url="https://888.com/",
                final_url="https://888.com/",
                depth=0,
                state="completed",
                html_evidence_id="evidence-page-001",
                screenshot_evidence_id="evidence-screenshot-001",
            )
        ],
        frontier=[
            CrawlFrontierRecord(
                id="frontier-888casino",
                depth=1,
                state="skipped",
                original_href="https://888casino.com/",
                normalized_url="https://888casino.com/",
                source_page_id="page-001",
                source_evidence_id="evidence-page-001",
                discovery_method="html_anchor",
                anchor_text="888casino",
                skip_reason="external_host_requires_approval",
            )
        ],
    )

    summary = run_live_investigation(
        result,
        tmp_path / "run",
        investigator=None,
        known_cases=[
            {
                "case_id": "case-888casino",
                "final_url_display": "https://888casino.com/",
                "public_status": "captured",
            }
        ],
        safety_policy=SafetyPolicy(),
    )

    graph = summary["graph"]
    assert isinstance(graph, dict)
    destination = next(node for node in graph["nodes"] if node["label"] == "888casino.com")
    assert destination["kind"] == "external_destination"
    assert destination["status"] == "collected"
    assert any(edge["relation"] == "publicly_links_to" for edge in graph["edges"])
    assert summary["pending_leads"] == []
