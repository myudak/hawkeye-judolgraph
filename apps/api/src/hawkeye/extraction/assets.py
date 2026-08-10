"""External script, image, iframe, and stylesheet domain extraction."""

from __future__ import annotations

from bs4 import BeautifulSoup

from .links import hostname_from_url, normalize_exact_asset_url
from .signals import ExtractedSignal


def extract_external_asset_domains(soup: BeautifulSoup, base_url: str) -> list[ExtractedSignal]:
    """Return external asset-host signals from known passive resource attributes."""

    base_hostname = hostname_from_url(base_url)
    candidates: list[tuple[str, str, str]] = []

    for element in soup.select("script[src]"):
        candidates.append(("script", "src", str(element.get("src", ""))))
    for element in soup.select("img[src]"):
        candidates.append(("image", "src", str(element.get("src", ""))))
    for element in soup.select("iframe[src]"):
        candidates.append(("iframe", "src", str(element.get("src", ""))))
    for element in soup.select("link[href]"):
        rel = element.get("rel", [])
        rel_values = (
            [str(item).lower() for item in rel] if isinstance(rel, list) else [str(rel).lower()]
        )
        if "stylesheet" in rel_values:
            candidates.append(("stylesheet", "href", str(element.get("href", ""))))

    signals: list[ExtractedSignal] = []
    for asset_type, attribute, raw_url in candidates:
        normalized = normalize_exact_asset_url(raw_url, base_url)
        if normalized is None:
            continue
        observed_url, canonical_url = normalized
        hostname = hostname_from_url(canonical_url)
        if hostname is None or hostname == base_hostname:
            continue
        signals.append(
            ExtractedSignal(
                type="external_asset_domain",
                value=hostname,
                normalized_value=hostname,
                extraction_method=f"html_{asset_type}_{attribute}",
                details={
                    "observed_asset_url": observed_url,
                    "canonical_asset_url": canonical_url,
                },
            )
        )
        signals.append(
            ExtractedSignal(
                type="external_asset_url",
                value=observed_url,
                normalized_value=canonical_url,
                extraction_method=f"html_{asset_type}_{attribute}",
                details={
                    "hostname": hostname,
                    "asset_type": asset_type,
                    "observed_asset_url": observed_url,
                    "canonical_asset_url": canonical_url,
                },
            )
        )
    return signals
