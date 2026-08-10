"""Compose all deterministic HTML extractors into evidence-linked entities."""

from __future__ import annotations

from bs4 import BeautifulSoup

from hawkeye.models import ExtractedEntity

from .assets import extract_external_asset_domains
from .links import extract_anchor_links
from .messaging import extract_telegram, extract_whatsapp
from .referrals import extract_referrals
from .signals import ExtractedSignal


def extract_entities(
    html: str,
    *,
    seed_url: str,
    final_url: str,
    source_evidence_id: str,
    entity_id_start: int = 1,
) -> list[ExtractedEntity]:
    """Extract required V0 signals and attach all of them to the saved HTML evidence."""

    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    links = extract_anchor_links(soup, final_url)
    signals: list[ExtractedSignal] = [
        ExtractedSignal(
            type="seed_url",
            value=seed_url,
            normalized_value=seed_url,
            extraction_method="collection_input",
        ),
        ExtractedSignal(
            type="final_url",
            value=final_url,
            normalized_value=final_url,
            extraction_method="browser_final_url",
        ),
    ]
    if title:
        signals.append(
            ExtractedSignal(
                type="page_title",
                value=title,
                normalized_value=title.casefold(),
                extraction_method="html_title",
            )
        )

    for link in links:
        link_details = {
            "anchor_text": link.anchor_text,
            "rel": link.rel,
            "source_region": link.source_region,
        }
        signals.extend(
            (
                ExtractedSignal(
                    type=link.kind,
                    value=link.url,
                    normalized_value=link.url,
                    extraction_method="html_anchor",
                    details=link_details,
                ),
                ExtractedSignal(
                    type="referenced_domain",
                    value=link.hostname,
                    normalized_value=link.hostname,
                    extraction_method="html_anchor",
                    details=link_details,
                ),
            )
        )

    signals.extend(extract_telegram(soup))
    signals.extend(extract_whatsapp(soup, final_url))
    signals.extend(extract_referrals([seed_url, final_url, *(link.url for link in links)]))
    signals.extend(extract_external_asset_domains(soup, final_url))

    unique_signals = _deduplicate_signals(signals)
    entities: list[ExtractedEntity] = []
    for index, signal in enumerate(unique_signals, start=entity_id_start):
        entities.append(
            ExtractedEntity(
                id=f"entity-{index:03d}",
                type=signal.type,
                value=signal.value,
                normalized_value=signal.normalized_value,
                source_evidence_id=source_evidence_id,
                source_url=final_url,
                extraction_method=signal.extraction_method,
                confidence=signal.confidence,
                details=signal.details,
            )
        )
    return entities


def _deduplicate_signals(signals: list[ExtractedSignal]) -> list[ExtractedSignal]:
    selected: dict[tuple[str, str], ExtractedSignal] = {}
    for signal in signals:
        key = (signal.type, signal.normalized_value)
        previous = selected.get(key)
        if previous is None or _signal_sort_key(signal) < _signal_sort_key(previous):
            selected[key] = signal
    return sorted(
        selected.values(),
        key=lambda signal: (signal.type, signal.normalized_value, signal.extraction_method),
    )


def _signal_sort_key(signal: ExtractedSignal) -> tuple[int, str, str, str]:
    return (signal.priority, signal.type, signal.normalized_value, signal.extraction_method)
