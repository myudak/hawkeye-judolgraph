"""Provenance-first extraction of public semantic observations from eligible captures."""

from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import parse_qsl, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag

from hawkeye.models import RedirectRecord, SemanticElementSnapshot, SemanticObservation

_EMAIL_RE = re.compile(r"(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", re.I)
_PHONE_RE = re.compile(r"(?<!\w)(\+?\d[\d\s().-]{7,}\d)(?!\w)")
_TELEGRAM_RE = re.compile(r"(?<!\w)@([A-Za-z][A-Za-z0-9_]{3,31})")
_WHATSAPP_PHONE_RE = re.compile(r"whats\s*app\s*[:\-]?\s*(\+?\d[\d\s().-]{7,}\d)", re.I)
_TELEGRAM_PHONE_RE = re.compile(r"telegram\s*[:\-]?\s*(\+?\d[\d\s().-]{7,}\d)", re.I)
_DOWNLOAD_EXTENSIONS = {
    ".apk",
    ".bin",
    ".dmg",
    ".exe",
    ".iso",
    ".msi",
    ".pkg",
    ".zip",
}
_PAYMENT_PROVIDERS = {
    "visa",
    "mastercard",
    "paypal",
    "gopay",
    "ovo",
    "dana",
    "qris",
    "shopeepay",
    "bank transfer",
}
_PAYMENT_METHODS = {"deposit", "withdrawal", "payment", "e-wallet", "bank transfer"}
_OFFER_TERMS = {"bonus", "promotion", "promo", "discount", "cashback", "special offer"}
_LEGAL_TERMS = {"licensed", "license", "licence", "regulated", "regulation"}
_REFERRAL_KEYS = {"ref", "referral", "affiliate", "aff", "invite", "promo", "refcode"}
_TRACKING_KEYS = {"gclid", "fbclid", "clickid", "campaign", "cid", "source"}


def extract_semantic_observations(
    html: str,
    *,
    source_page_id: str,
    source_url: str,
    source_artifact_id: str,
    screenshot_evidence_id: str,
    semantic_elements: Iterable[SemanticElementSnapshot] = (),
    redirects: Iterable[RedirectRecord] = (),
    observation_id_start: int = 1,
) -> list[SemanticObservation]:
    """Extract bounded observations while preserving raw values and exact source artifacts."""

    soup = BeautifulSoup(html, "html.parser")
    snapshots = list(semantic_elements)
    observations: list[SemanticObservation] = []
    seen: set[tuple[str, str, str | None]] = set()

    def add(
        observation_type: str,
        raw_value: str,
        *,
        normalized_value: str | None = None,
        element: Tag | None = None,
        selector: str | None = None,
        surrounding_text: str | None = None,
        confidence: float = 1.0,
        extraction_method: str = "dom_text",
        evidence_strength: str = "moderate",
        attributes: dict[str, object] | None = None,
    ) -> None:
        raw = _bounded(raw_value, 2000)
        normalized = _bounded(normalized_value or _normalize_text(raw), 2000)
        snapshot = _match_snapshot(element, snapshots)
        chosen_selector = selector or (snapshot.selector if snapshot else None)
        key = (observation_type, normalized, chosen_selector)
        if not raw or key in seen or len(observations) >= 500:
            return
        seen.add(key)
        context = surrounding_text
        if context is None and element is not None:
            context = (
                element.parent.get_text(" ", strip=True)
                if element.parent
                else element.get_text(" ", strip=True)
            )
        observations.append(
            SemanticObservation(
                id=f"observation-{observation_id_start + len(observations):04d}",
                observation_type=observation_type,  # type: ignore[arg-type]
                raw_value=raw,
                normalized_value=normalized,
                source_page_id=source_page_id,
                source_url=source_url,
                source_artifact_id=source_artifact_id,
                selector=chosen_selector,
                surrounding_text=_bounded(context or "", 1000),
                screenshot_evidence_id=screenshot_evidence_id,
                crop_coordinates=(
                    {
                        "x": snapshot.x,
                        "y": snapshot.y,
                        "width": snapshot.width,
                        "height": snapshot.height,
                    }
                    if snapshot
                    else None
                ),
                confidence=confidence,
                extraction_method=extraction_method,
                evidence_strength=evidence_strength,  # type: ignore[arg-type]
                attributes=attributes or {},
            )
        )

    _extract_claimed_brand(soup, add)

    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href", "")).strip()
        destination = urljoin(source_url, href)
        split = urlsplit(destination)
        label = anchor.get_text(" ", strip=True)
        attributes = {
            "visible_label": _bounded(label, 500),
            "destination": destination,
            "normalized_destination": _normalize_url(destination),
            "relation_type": "public_anchor",
            "target": str(anchor.get("target", "")),
            "new_tab": str(anchor.get("target", "")).casefold() == "_blank",
            "download_attribute": anchor.has_attr("download"),
            "destination_permitted": split.scheme in {"http", "https"},
        }
        if split.scheme in {"http", "https"}:
            add(
                "public_outgoing_link",
                destination,
                normalized_value=_normalize_url(destination),
                element=anchor,
                extraction_method="dom_anchor",
                evidence_strength="strong",
                attributes=attributes,
            )
        hostname = (split.hostname or "").casefold()
        path_parts = [part for part in split.path.split("/") if part]
        if hostname in {"t.me", "telegram.me", "www.t.me"} and path_parts:
            alias = path_parts[0].lstrip("@").casefold()
            telegram_type = (
                "public_telegram_contact"
                if _digits(alias) and len(_digits(alias)) >= 8
                else "public_telegram_alias"
            )
            add(
                telegram_type,
                href,
                normalized_value=(
                    f"+{_digits(alias)}"
                    if telegram_type == "public_telegram_contact"
                    else f"@{alias}"
                ),
                element=anchor,
                extraction_method="dom_anchor_telegram",
                evidence_strength="strong",
            )
        if hostname in {"wa.me", "api.whatsapp.com", "web.whatsapp.com"}:
            number = _digits("".join(path_parts) or dict(parse_qsl(split.query)).get("phone", ""))
            add(
                "public_whatsapp_link",
                href,
                normalized_value=f"https://wa.me/{number}"
                if number
                else _normalize_url(destination),
                element=anchor,
                extraction_method="dom_anchor_whatsapp",
                evidence_strength="strong",
            )
        if anchor.has_attr("download") or split.path.casefold().endswith(
            tuple(_DOWNLOAD_EXTENSIONS)
        ):
            add(
                "public_download_destination",
                destination,
                normalized_value=_normalize_url(destination),
                element=anchor,
                extraction_method="dom_download_inspection",
                evidence_strength="strong",
                attributes={**attributes, "navigation_blocked": True},
            )
        for key, value in parse_qsl(split.query, keep_blank_values=False):
            normalized_key = key.casefold()
            if normalized_key in _REFERRAL_KEYS:
                add(
                    "public_referral_code",
                    value,
                    normalized_value=value.strip().casefold(),
                    element=anchor,
                    extraction_method=f"url_query:{normalized_key}",
                    evidence_strength="strong",
                    attributes={"parameter": normalized_key, "destination": destination},
                )
            if normalized_key.startswith("utm_") or normalized_key in _TRACKING_KEYS:
                add(
                    "public_tracking_identifier",
                    f"{key}={value}",
                    normalized_value=f"{normalized_key}={value.strip().casefold()}",
                    element=anchor,
                    extraction_method="url_tracking_parameter",
                    evidence_strength="moderate",
                    attributes={"parameter": normalized_key, "destination": destination},
                )

    visible_text = soup.get_text(" ", strip=True)
    channel_phone_spans: list[tuple[int, int]] = []
    for match in _WHATSAPP_PHONE_RE.finditer(visible_text):
        value = match.group(1)
        digits = _digits(value)
        if len(digits) >= 8:
            channel_phone_spans.append(match.span(1))
            add(
                "public_whatsapp_link",
                value,
                normalized_value=f"https://wa.me/{digits}",
                surrounding_text=_context(visible_text, match.start(1), match.end(1)),
                confidence=0.9,
                extraction_method="visible_text_channel_label",
                evidence_strength="strong",
            )
    for match in _TELEGRAM_PHONE_RE.finditer(visible_text):
        value = match.group(1)
        digits = _digits(value)
        if len(digits) >= 8:
            channel_phone_spans.append(match.span(1))
            add(
                "public_telegram_contact",
                value,
                normalized_value=f"+{digits}",
                surrounding_text=_context(visible_text, match.start(1), match.end(1)),
                confidence=0.9,
                extraction_method="visible_text_channel_label",
                evidence_strength="strong",
            )
    for match in _EMAIL_RE.finditer(visible_text):
        value = match.group(1)
        add(
            "public_email_address",
            value,
            normalized_value=value.casefold(),
            surrounding_text=_context(visible_text, match.start(), match.end()),
            extraction_method="visible_text_regex",
            evidence_strength="strong",
        )
    for match in _PHONE_RE.finditer(visible_text):
        if any(
            start <= match.start(1) and match.end(1) <= end for start, end in channel_phone_spans
        ):
            continue
        value = match.group(1)
        digits = _digits(value)
        if len(digits) >= 8:
            add(
                "public_phone_number",
                value,
                normalized_value=f"+{digits}" if value.strip().startswith("+") else digits,
                surrounding_text=_context(visible_text, match.start(), match.end()),
                extraction_method="visible_text_regex",
                evidence_strength="moderate",
            )
    for match in _TELEGRAM_RE.finditer(visible_text):
        add(
            "public_telegram_alias",
            match.group(0),
            normalized_value=f"@{match.group(1).casefold()}",
            surrounding_text=_context(visible_text, match.start(), match.end()),
            confidence=0.9,
            extraction_method="visible_text_regex",
            evidence_strength="moderate",
        )

    _extract_claim_terms(visible_text, _PAYMENT_METHODS, "public_payment_method", add)
    _extract_claim_terms(visible_text, _PAYMENT_PROVIDERS, "public_payment_provider", add)
    _extract_claim_terms(visible_text, _OFFER_TERMS, "public_offer_claim", add)
    _extract_claim_terms(visible_text, _LEGAL_TERMS, "public_legal_or_license_claim", add)

    for redirect in redirects:
        add(
            "public_redirect_target",
            redirect.destination_url,
            normalized_value=_normalize_url(redirect.destination_url),
            surrounding_text=f"Redirect observed from {redirect.source_url}",
            confidence=1.0,
            extraction_method="network_redirect",
            evidence_strength="strong",
            attributes={
                "source_url": redirect.source_url,
                "status_code": redirect.status_code,
                "raw_location": redirect.raw_location,
            },
        )
    return observations


def _extract_claimed_brand(soup: BeautifulSoup, add: object) -> None:
    callback = add  # keep the nested callback readable without widening the public API
    candidates: list[tuple[str, Tag | None, str]] = []
    meta = soup.find("meta", attrs={"property": "og:site_name"})
    if isinstance(meta, Tag) and meta.get("content"):
        candidates.append((str(meta.get("content")), meta, "meta_og_site_name"))
    heading = soup.find("h1")
    if isinstance(heading, Tag):
        candidates.append((heading.get_text(" ", strip=True), heading, "dom_h1"))
    if soup.title:
        candidates.append((soup.title.get_text(" ", strip=True), soup.title, "document_title"))
    for value, element, method in candidates[:3]:
        if value:
            callback(  # type: ignore[operator]
                "claimed_brand_identity",
                value,
                normalized_value=_normalize_text(value),
                element=element,
                confidence=0.85 if method != "meta_og_site_name" else 0.95,
                extraction_method=method,
                evidence_strength="moderate",
                attributes={"entity_class": "ClaimedBrandIdentity", "verified_ownership": False},
            )


def _extract_claim_terms(text: str, terms: set[str], observation_type: str, add: object) -> None:
    folded = text.casefold()
    for term in sorted(terms):
        start = folded.find(term)
        if start >= 0:
            add(  # type: ignore[operator]
                observation_type,
                term,
                normalized_value=term,
                surrounding_text=_context(text, start, start + len(term)),
                confidence=0.75,
                extraction_method="visible_text_dictionary",
                evidence_strength="weak",
                attributes={"public_claim_only": True},
            )


def _match_snapshot(
    element: Tag | None, snapshots: list[SemanticElementSnapshot]
) -> SemanticElementSnapshot | None:
    if element is None:
        return None
    href = str(element.get("href", "")) if element.name == "a" else None
    text = element.get_text(" ", strip=True)[:200]
    for snapshot in snapshots:
        if href and snapshot.href and urlsplit(snapshot.href).path == urlsplit(href).path:
            return snapshot
        if text and snapshot.visible_text == text:
            return snapshot
    return None


def _normalize_url(value: str) -> str:
    split = urlsplit(value)
    host = (split.hostname or "").casefold()
    netloc = host
    if split.port and not (
        (split.scheme.casefold() == "http" and split.port == 80)
        or (split.scheme.casefold() == "https" and split.port == 443)
    ):
        netloc = f"{host}:{split.port}"
    return urlunsplit((split.scheme.casefold(), netloc, split.path or "/", split.query, ""))


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _digits(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


def _context(text: str, start: int, end: int) -> str:
    return _bounded(text[max(0, start - 120) : min(len(text), end + 120)], 300)


def _bounded(value: str, limit: int) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", value).strip()[:limit]
