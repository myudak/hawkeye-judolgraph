"""Evidence-count gambling indicator classification tests."""

from __future__ import annotations

from hawkeye.indicators import classify_gambling_indicators
from hawkeye.models import SemanticObservation


def _observation(
    ordinal: int,
    observation_type: str,
    value: str,
    *,
    page_id: str = "page-001",
    surrounding_text: str = "",
) -> SemanticObservation:
    return SemanticObservation.model_validate(
        {
            "id": f"observation-{ordinal:04d}",
            "observation_type": observation_type,
            "raw_value": value,
            "normalized_value": value.casefold(),
            "source_page_id": page_id,
            "source_url": f"https://evidence.invalid/{page_id}",
            "source_artifact_id": f"evidence-{page_id}",
            "surrounding_text": surrounding_text,
            "screenshot_evidence_id": f"screenshot-{page_id}",
            "confidence": 0.9,
            "extraction_method": "fixture",
            "evidence_strength": "strong",
        }
    )


def test_counts_direct_and_contextual_indicators_without_percentage() -> None:
    observations = [
        _observation(1, "public_offer_claim", "Bonus slot jackpot"),
        _observation(2, "public_payment_provider", "DANA"),
        _observation(3, "public_phone_number", "+62000000000"),
    ]

    summary = classify_gambling_indicators(observations)

    assert summary.status == "indicators_observed"
    assert summary.indicator_count == 2
    assert summary.reviewed_observation_count == 3
    assert summary.category_counts == {
        "gambling_offer": 1,
        "transaction_enablement": 1,
    }
    assert [item.label for item in summary.classifications] == [
        "indicator",
        "indicator",
        "not_indicator",
    ]
    assert "percentage" not in summary.model_dump()
    assert "probability" not in summary.model_dump()


def test_generic_contact_payment_and_link_do_not_imply_gambling() -> None:
    observations = [
        _observation(1, "public_payment_provider", "DANA"),
        _observation(2, "public_whatsapp_link", "https://wa.me/62000000000"),
        _observation(3, "public_outgoing_link", "https://example.invalid/support"),
    ]

    summary = classify_gambling_indicators(observations)

    assert summary.status == "no_indicators_observed"
    assert summary.indicator_count == 0
    assert all(item.label == "not_indicator" for item in summary.classifications)
    assert summary.osint_counts == {
        "links_and_destinations": 1,
        "payments_and_offers": 1,
        "public_contacts": 1,
    }


def test_empty_observations_are_insufficient_not_negative_proof() -> None:
    summary = classify_gambling_indicators([])

    assert summary.status == "insufficient_evidence"
    assert summary.indicator_count == 0
    assert summary.reviewed_observation_count == 0
