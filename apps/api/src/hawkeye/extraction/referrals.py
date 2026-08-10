"""Referral-query extraction from normalized anchor destinations."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlsplit

from .signals import ExtractedSignal

REFERRAL_PARAMETER_NAMES = {"ref", "referral", "affiliate", "aff", "invite"}


def extract_referrals(urls: list[str]) -> list[ExtractedSignal]:
    """Extract recognized non-empty referral query parameters from URLs."""

    signals: list[ExtractedSignal] = []
    for url in urls:
        for raw_key, raw_value in parse_qsl(urlsplit(url).query, keep_blank_values=False):
            key = raw_key.lower()
            value = raw_value.strip()
            if key not in REFERRAL_PARAMETER_NAMES or not value:
                continue
            normalized = f"{key}={value}"
            signals.append(
                ExtractedSignal(
                    type="referral",
                    value=normalized,
                    normalized_value=normalized,
                    extraction_method="url_query_parameter",
                    details={"parameter": key, "destination_url": url},
                )
            )
    return signals
