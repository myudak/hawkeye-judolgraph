"""Classify captured pages without using an LLM or bypassing restrictions."""

from __future__ import annotations

import re

from hawkeye.models import CaptureClassification, CaptureOutcome

_MAX_ANALYZED_TEXT_LENGTH = 50_000
_MIN_MEANINGFUL_TEXT_LENGTH = 24
_MIN_MEANINGFUL_WORDS = 4

_BOT_CHALLENGE_STRONG = (
    "just a moment",
    "checking your browser",
    "verify you are human",
    "performing security verification",
    "attention required",
    "security verification",
)
_BOT_CHALLENGE_WEAK = ("cloudflare", "browser verification", "security check")
_BOT_CHALLENGE_URL_MARKERS = ("__cf_chl_", "challenge-platform")
_GEO_RESTRICTED = (
    "not available in your country",
    "not available in your region",
    "not available in this region",
    "not available in your jurisdiction",
    "location restricted",
    "geo-restricted",
)
_UNAVAILABLE = (
    "page unavailable",
    "unavailable page",
    "website currently unavailable",
    "site is unavailable",
    "temporarily unavailable",
    "service unavailable in your region",
)
_CONSENT = (
    "manage consent",
    "cookie preferences",
    "accept all cookies",
    "reject non-essential",
    "privacy choices",
    "consent preferences",
)
_UNKNOWN_RESTRICTION = (
    "access denied",
    "request blocked",
    "unusual traffic",
    "restricted access",
    "automated requests are not allowed",
)


def classify_capture(
    *,
    title: str | None,
    final_url: str | None,
    visible_text: str,
    navigation_status: str,
    error_type: str | None = None,
) -> CaptureClassification:
    """Return a deterministic, conservative assessment of one navigation result.

    The explicit precedence is timeout, navigation error, bot challenge, geo restriction,
    unavailable page, consent wall, unknown restriction, then normal content.
    """

    normalized_status = _normalize(navigation_status)
    normalized_error = _normalize(error_type or "")
    if normalized_status in {"timed_out", "timeout"} or "timeout" in normalized_error:
        return _restricted(CaptureOutcome.TIMEOUT, "navigation timed out")
    if normalized_status not in {"captured", "completed"} or normalized_error:
        reason = "navigation did not complete"
        if normalized_error:
            reason = f"navigation error type: {normalized_error.split(':', maxsplit=1)[0]}"
        return _restricted(CaptureOutcome.NAVIGATION_ERROR, reason)

    normalized_title = _normalize(title or "")
    normalized_text = _normalize(visible_text)[:_MAX_ANALYZED_TEXT_LENGTH]
    combined = " ".join(part for part in (normalized_title, normalized_text) if part)
    normalized_url = _normalize(final_url or "")

    bot_reasons = _match_reasons(combined, _BOT_CHALLENGE_STRONG, "bot-challenge indicator")
    url_reasons = _match_reasons(
        normalized_url, _BOT_CHALLENGE_URL_MARKERS, "bot-challenge URL marker"
    )
    weak_bot_reasons = _match_reasons(combined, _BOT_CHALLENGE_WEAK, "bot-challenge indicator")
    if bot_reasons or url_reasons or len(weak_bot_reasons) >= 2:
        return _restricted(
            CaptureOutcome.BOT_CHALLENGE, *(bot_reasons or url_reasons or weak_bot_reasons)
        )

    geo_reasons = _match_reasons(combined, _GEO_RESTRICTED, "geo-restriction indicator")
    if geo_reasons:
        return _restricted(CaptureOutcome.GEO_RESTRICTED, *geo_reasons)

    unavailable_reasons = _match_reasons(combined, _UNAVAILABLE, "unavailable-page indicator")
    if unavailable_reasons:
        return _restricted(CaptureOutcome.UNAVAILABLE_PAGE, *unavailable_reasons)

    consent_reasons = _match_reasons(combined, _CONSENT, "consent-wall indicator")
    if len(consent_reasons) >= 2 and not _has_meaningful_non_consent_content(normalized_text):
        return _restricted(CaptureOutcome.CONSENT_WALL, *consent_reasons)

    unknown_reasons = _match_reasons(combined, _UNKNOWN_RESTRICTION, "restriction indicator")
    if unknown_reasons:
        return _restricted(CaptureOutcome.UNKNOWN_RESTRICTION, *unknown_reasons)
    if not _has_meaningful_content(normalized_text):
        return _restricted(
            CaptureOutcome.UNKNOWN_RESTRICTION, "captured page had no meaningful visible text"
        )

    return CaptureClassification(outcome=CaptureOutcome.CONTENT, content_usable=True, reasons=[])


def _restricted(outcome: CaptureOutcome, *reasons: str) -> CaptureClassification:
    return CaptureClassification(outcome=outcome, content_usable=False, reasons=list(reasons))


def _match_reasons(content: str, indicators: tuple[str, ...], label: str) -> list[str]:
    return [f"{label}: {indicator}" for indicator in indicators if indicator in content]


def _has_meaningful_content(text: str) -> bool:
    return len(text) >= _MIN_MEANINGFUL_TEXT_LENGTH and len(text.split()) >= _MIN_MEANINGFUL_WORDS


def _has_meaningful_non_consent_content(text: str) -> bool:
    remaining = text
    for indicator in _CONSENT:
        remaining = remaining.replace(indicator, " ")
    return len(remaining.strip()) >= 160 or len(remaining.split()) >= 20


def _normalize(value: str) -> str:
    controls_removed = re.sub(r"[\x00-\x1f\x7f]", " ", value)
    return re.sub(r"\s+", " ", controls_removed).strip().casefold()
