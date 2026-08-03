"""G4B provenance-first semantic observation coverage."""

from __future__ import annotations

import json
from pathlib import Path

from hawkeye.collector.safety import SafetyPolicy
from hawkeye.models import SemanticObservation
from hawkeye.pipeline import investigate
from hawkeye.semantic_evidence import extract_semantic_observations


def test_semantic_observation_types_normalization_provenance_and_crops(
    fixture_server_url: str, tmp_path: Path
) -> None:
    result = investigate(
        f"{fixture_server_url}semantic-evidence.html",
        output=tmp_path / "cases",
        case_id="semantic-evidence",
        timeout_seconds=15,
        case_timeout_seconds=30,
        max_pages=1,
        max_depth=0,
        safety_policy=SafetyPolicy(allow_loopback_for_testing=True),
    )
    root = Path(result.case_directory)
    observations = result.observations
    types = {item.observation_type for item in observations}
    assert {
        "claimed_brand_identity",
        "public_telegram_alias",
        "public_whatsapp_link",
        "public_phone_number",
        "public_email_address",
        "public_outgoing_link",
        "public_download_destination",
        "public_payment_method",
        "public_payment_provider",
        "public_offer_claim",
        "public_legal_or_license_claim",
        "public_referral_code",
        "public_tracking_identifier",
    } <= types
    telegram = next(
        item for item in observations if item.observation_type == "public_telegram_alias"
    )
    assert telegram.normalized_value == "@exampledesk"
    assert telegram.source_artifact_id == "evidence-page-001"
    assert telegram.screenshot_evidence_id == "evidence-screenshot-001"
    assert telegram.extraction_method
    assert telegram.surrounding_text
    assert any(item.crop_evidence_id for item in observations)
    crop_ids = {item.crop_evidence_id for item in observations if item.crop_evidence_id}
    stored = [
        SemanticObservation.model_validate(item)
        for item in json.loads((root / "observations.json").read_text("utf-8"))
    ]
    assert crop_ids
    assert (root / "observations.json").is_file()
    assert any((root / "crops").glob("*.png"))
    assert stored == observations


def test_information_rich_unstable_capture_extracts_only_provisional_observations(
    fixture_server_url: str, tmp_path: Path
) -> None:
    result = investigate(
        f"{fixture_server_url}render-never-settles.html",
        output=tmp_path / "cases",
        case_id="limited-no-semantic-extraction",
        timeout_seconds=15,
        case_timeout_seconds=30,
        max_pages=1,
        max_depth=0,
        safety_policy=SafetyPolicy(allow_loopback_for_testing=True),
    )
    assert result.case.capture_adequacy.value == "limited"
    assert result.case.extraction_eligible is True
    assert result.case.extraction_tier == "provisional"
    assert result.observations
    assert all(item.attributes.get("provisional") is True for item in result.observations)
    assert all(
        "provisional_observation_from_limited_capture" in item.limitations
        for item in result.observations
    )


def test_channel_labeled_phone_numbers_become_real_contact_evidence() -> None:
    html = """
    <html><body>
      <section><h2>Nomor Kontak</h2><p>+639543355092</p></section>
      <section><h2>Whats App</h2><p>+639543355092</p></section>
      <section><h2>Telegram</h2><p>+639157800101</p></section>
    </body></html>
    """
    observations = extract_semantic_observations(
        html,
        source_page_id="route-contact",
        source_url="https://example.test/Contact",
        source_artifact_id="interaction-001.html",
        screenshot_evidence_id="interaction-001.png",
    )

    assert any(
        item.observation_type == "public_whatsapp_link"
        and item.normalized_value == "https://wa.me/639543355092"
        for item in observations
    )
    assert any(
        item.observation_type == "public_telegram_contact"
        and item.normalized_value == "+639157800101"
        for item in observations
    )
    assert {
        item.normalized_value
        for item in observations
        if item.observation_type == "public_phone_number"
    } == {"+639543355092"}
    assert [
        item.normalized_value
        for item in observations
        if item.observation_type == "public_whatsapp_link"
    ] == ["https://wa.me/639543355092"]
    assert [
        item.normalized_value
        for item in observations
        if item.observation_type == "public_telegram_contact"
    ] == ["+639157800101"]
