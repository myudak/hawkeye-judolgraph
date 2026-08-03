"""G5 exactly-ten scenario, stable-reference, budget, and unsafe-block tests."""

from __future__ import annotations

from hawkeye.interaction import ControlledPageSession, load_controlled_scenarios
from hawkeye.interaction.models import InteractiveElement
from hawkeye.interaction.policy import validate_read_only_interaction


def test_fixture_manifest_has_exactly_ten_required_scenarios() -> None:
    scenarios = load_controlled_scenarios()
    assert len(scenarios) == 10
    assert [item.ordinal for item in scenarios] == list(range(1, 11))
    assert [item.name for item in scenarios] == [
        "Visible evidence with no interaction",
        "Modal revealed by safe button",
        "Menu revealed by safe button",
        "Tab with hidden public content",
        "Iframe with public child content",
        "Redirect or new-tab destination",
        "Ambiguous button",
        "Login and Register unsafe distractors",
        "Download unsafe distractor",
        "No useful hidden evidence",
    ]


def test_all_safe_required_interactions_reveal_only_expected_public_observables() -> None:
    for scenario in load_controlled_scenarios():
        session = ControlledPageSession(scenario)
        if scenario.required_interaction is None:
            assert (
                scenario.expected_observable in session.page_get_state().observations
                or scenario.expected_observable is None
            )
            continue
        reference = next(
            item
            for item in session.page_list_interactive_elements()
            if item.element_id == scenario.required_interaction
        )
        decision = (
            session.page_open_public_link(reference)
            if scenario.scenario_id == "redirect-new-tab"
            else session.page_click_read_only(reference)
        )
        assert decision.status == "completed"
        if scenario.expected_observable is not None:
            assert scenario.expected_observable in decision.observations


def test_unsafe_action_block_rate_is_one_hundred_percent() -> None:
    unsafe_count = 0
    blocked_count = 0
    for scenario in load_controlled_scenarios():
        session = ControlledPageSession(scenario)
        references = {item.element_id: item for item in session.page_list_interactive_elements()}
        for element_id in scenario.unsafe_control_ids:
            unsafe_count += 1
            decision = session.page_click_read_only(references[element_id])
            blocked_count += decision.status == "blocked"
            assert decision.policy_checks["element_type"]
            assert decision.policy_checks["current_page_state"] == "snapshot-001"
    assert unsafe_count == 4
    assert blocked_count / unsafe_count == 1.0


def test_reference_is_rejected_after_state_changes() -> None:
    scenario = load_controlled_scenarios()[1]
    session = ControlledPageSession(scenario)
    reference = session.page_list_interactive_elements()[0]
    assert session.page_click_read_only(reference).status == "completed"
    assert session.page_click_read_only(reference).status == "stale_reference"


def test_default_budget_contract_and_narrow_tools() -> None:
    scenario = load_controlled_scenarios()[-1]
    session = ControlledPageSession(scenario)
    assert session.budget.model_dump() == {
        "max_iterations": 5,
        "max_interactions": 3,
        "max_pages": 3,
        "max_depth": 1,
        "max_redirects": 5,
        "max_search_queries": 1,
        "max_candidate_pages": 3,
        "max_runtime_seconds": 120,
    }
    assert session.page_capture_state().tool_name == "page_capture_state"
    assert session.page_get_redirect_chain().tool_name == "page_get_redirect_chain"


def test_contact_information_route_is_safe_but_live_chat_remains_blocked() -> None:
    contact = InteractiveElement(
        element_id="contact",
        dom_path="a.contact",
        role="link",
        tag="a",
        accessible_name="Contact Us",
        visible_text="Contact Us",
        declared_behavior="reveal_tab",
    )
    chat = contact.model_copy(
        update={
            "element_id": "chat",
            "dom_path": "button.chat",
            "tag": "button",
            "role": "button",
            "accessible_name": "Live Chat",
            "visible_text": "Live Chat",
        }
    )

    assert validate_read_only_interaction(contact)[:2] == (
        True,
        "validated_public_reveal",
    )
    assert validate_read_only_interaction(chat)[:2] == (
        False,
        "forbidden_action_keyword",
    )
