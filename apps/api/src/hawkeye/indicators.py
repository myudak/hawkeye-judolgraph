"""Explainable evidence-count indicators for public gambling-related content."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Literal

from pydantic import BaseModel, Field

from hawkeye.models import SemanticObservation

INDICATOR_POLICY_VERSION = "gambling-evidence-count-v1"

_TERM_GROUPS: dict[str, tuple[str, ...]] = {
    "wagering_language": (
        "bet",
        "betting",
        "casino",
        "gambling",
        "judi",
        "judol",
        "poker",
        "sportsbook",
        "taruhan",
        "togel",
        "wager",
    ),
    "game_mechanics": (
        "baccarat",
        "blackjack",
        "free spin",
        "gacor",
        "jackpot",
        "live casino",
        "maxwin",
        "roulette",
        "rtp",
        "slot",
        "slots",
    ),
    "betting_promotion": (
        "bonus deposit",
        "bonus new member",
        "cashback",
        "parlay",
        "promo deposit",
        "turnover",
    ),
}

_CONTEXTUAL_TYPES = {
    "public_offer_claim": "gambling_offer",
    "public_payment_method": "transaction_enablement",
    "public_payment_provider": "transaction_enablement",
    "public_referral_code": "referral_or_tracking",
    "public_tracking_identifier": "referral_or_tracking",
}

_OSINT_GROUP_BY_TYPE = {
    "public_telegram_alias": "public_contacts",
    "public_telegram_contact": "public_contacts",
    "public_whatsapp_link": "public_contacts",
    "public_phone_number": "public_contacts",
    "public_email_address": "public_contacts",
    "public_outgoing_link": "links_and_destinations",
    "public_redirect_target": "links_and_destinations",
    "public_download_destination": "links_and_destinations",
    "public_payment_method": "payments_and_offers",
    "public_payment_provider": "payments_and_offers",
    "public_offer_claim": "payments_and_offers",
    "public_referral_code": "referrals_and_tracking",
    "public_tracking_identifier": "referrals_and_tracking",
    "claimed_brand_identity": "public_claims",
    "public_legal_or_license_claim": "public_claims",
}


class EvidenceIndicatorClassification(BaseModel):
    """One observation-level classification with immutable evidence references."""

    observation_id: str
    observation_type: str
    label: Literal["indicator", "not_indicator"]
    category: str | None = None
    matched_terms: list[str] = Field(default_factory=list)
    rationale: str
    source_page_id: str
    source_artifact_id: str
    screenshot_evidence_id: str


class GamblingIndicatorSummary(BaseModel):
    """Count-based OSINT signal summary; deliberately not a probability or verdict."""

    policy_version: str = INDICATOR_POLICY_VERSION
    status: Literal[
        "indicators_observed",
        "no_indicators_observed",
        "insufficient_evidence",
    ]
    indicator_count: int = Field(ge=0)
    reviewed_observation_count: int = Field(ge=0)
    category_counts: dict[str, int] = Field(default_factory=dict)
    osint_counts: dict[str, int] = Field(default_factory=dict)
    classifications: list[EvidenceIndicatorClassification] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


def classify_gambling_indicators(
    observations: list[SemanticObservation],
) -> GamblingIndicatorSummary:
    """Classify each verified observation and count evidence-backed indicators.

    Direct gambling language is sufficient for an indicator. Generic payment, offer, referral,
    or tracking observations count only when another observation from the same captured page
    carries direct gambling language. Contacts and links remain useful OSINT but never become
    gambling indicators merely because they appear beside a matched item.
    """

    page_terms: dict[str, set[str]] = defaultdict(set)
    direct_terms: dict[str, set[str]] = {}
    for observation in observations:
        terms = _matched_terms(_observation_text(observation))
        direct_terms[observation.id] = terms
        page_terms[observation.source_page_id].update(terms)

    classifications: list[EvidenceIndicatorClassification] = []
    categories: Counter[str] = Counter()
    osint_counts: Counter[str] = Counter()
    for observation in observations:
        osint_counts[
            _OSINT_GROUP_BY_TYPE.get(observation.observation_type, "other_observations")
        ] += 1
        terms = direct_terms[observation.id]
        category: str | None = None
        rationale = "No controlled gambling-language signal matched this observation."
        if terms:
            category = _direct_category(observation, terms)
            rationale = "Matched controlled gambling-language terms in this public observation."
        elif (
            observation.observation_type in _CONTEXTUAL_TYPES
            and page_terms[observation.source_page_id]
        ):
            category = _CONTEXTUAL_TYPES[observation.observation_type]
            terms = page_terms[observation.source_page_id]
            rationale = (
                "Typed transaction, offer, referral, or tracking evidence appears on a captured "
                "page with direct gambling-language evidence."
            )

        if category is not None:
            categories[category] += 1
        classifications.append(
            EvidenceIndicatorClassification(
                observation_id=observation.id,
                observation_type=observation.observation_type,
                label="indicator" if category is not None else "not_indicator",
                category=category,
                matched_terms=sorted(terms),
                rationale=rationale,
                source_page_id=observation.source_page_id,
                source_artifact_id=observation.source_artifact_id,
                screenshot_evidence_id=observation.screenshot_evidence_id,
            )
        )

    indicator_count = sum(categories.values())
    status: Literal[
        "indicators_observed",
        "no_indicators_observed",
        "insufficient_evidence",
    ] = (
        "insufficient_evidence"
        if not observations
        else "indicators_observed"
        if indicator_count
        else "no_indicators_observed"
    )
    limitations = [
        "Counts describe matched public evidence items, not a percentage or probability.",
        "An indicator is not a finding of ownership, operator identity, criminality, or legality.",
        "Unmatched, inaccessible, image-only, or locale-dependent content may not be classified.",
    ]
    return GamblingIndicatorSummary(
        status=status,
        indicator_count=indicator_count,
        reviewed_observation_count=len(observations),
        category_counts=dict(sorted(categories.items())),
        osint_counts=dict(sorted(osint_counts.items())),
        classifications=classifications,
        limitations=limitations,
    )


def _observation_text(observation: SemanticObservation) -> str:
    return " ".join(
        (
            observation.raw_value,
            observation.normalized_value,
            observation.surrounding_text,
        )
    ).casefold()


def _matched_terms(text: str) -> set[str]:
    matched: set[str] = set()
    for terms in _TERM_GROUPS.values():
        for term in terms:
            pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
            if re.search(pattern, text):
                matched.add(term)
    return matched


def _direct_category(observation: SemanticObservation, terms: set[str]) -> str:
    if observation.observation_type == "claimed_brand_identity":
        return "gambling_brand_claim"
    if observation.observation_type == "public_offer_claim":
        return "gambling_offer"
    if observation.observation_type in {"public_payment_method", "public_payment_provider"}:
        return "transaction_enablement"
    if any(term in _TERM_GROUPS["game_mechanics"] for term in terms):
        return "game_mechanics"
    if any(term in _TERM_GROUPS["betting_promotion"] for term in terms):
        return "gambling_offer"
    return "wagering_language"
