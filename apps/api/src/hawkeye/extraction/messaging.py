"""Telegram and WhatsApp/phone signal extraction."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup

from .signals import ExtractedSignal

_TELEGRAM_HANDLE_RE = re.compile(r"(?<![\w@])@([A-Za-z][A-Za-z0-9_]{4,31})\b")
_TELEGRAM_HOSTS = {"t.me", "www.t.me", "telegram.me", "www.telegram.me"}
_WHATSAPP_HOSTS = {"wa.me", "www.wa.me", "api.whatsapp.com", "web.whatsapp.com"}


def extract_telegram(soup: BeautifulSoup) -> list[ExtractedSignal]:
    """Find Telegram links first, then public plain-text handles."""

    signals: list[ExtractedSignal] = []
    for anchor in soup.select("a[href]"):
        href = anchor.get("href")
        if not isinstance(href, str):
            continue
        handle = _telegram_handle_from_url(href)
        if handle:
            signals.append(
                ExtractedSignal(
                    type="telegram",
                    value=f"@{handle}",
                    normalized_value=f"@{handle.lower()}",
                    extraction_method="html_anchor",
                    priority=0,
                )
            )

    text = soup.get_text(" ", strip=True)
    for match in _TELEGRAM_HANDLE_RE.finditer(text):
        handle = match.group(1)
        signals.append(
            ExtractedSignal(
                type="telegram",
                value=f"@{handle}",
                normalized_value=f"@{handle.lower()}",
                extraction_method="plain_text_regex",
                priority=1,
            )
        )
    return signals


def extract_whatsapp(soup: BeautifulSoup, base_url: str) -> list[ExtractedSignal]:
    """Extract WhatsApp destinations and phone-like values carried by their URLs."""

    signals: list[ExtractedSignal] = []
    for anchor in soup.select("a[href]"):
        href = anchor.get("href")
        if not isinstance(href, str):
            continue
        normalized_href = urljoin(base_url, href.strip())
        parsed = urlsplit(normalized_href)
        host = (parsed.hostname or "").lower()
        if parsed.scheme == "whatsapp" or host in _WHATSAPP_HOSTS:
            phone = _phone_from_whatsapp_url(normalized_href)
            if phone:
                value = f"+{phone}"
                signals.append(
                    ExtractedSignal(
                        type="whatsapp_or_phone",
                        value=value,
                        normalized_value=value,
                        extraction_method="html_anchor",
                        details={"whatsapp_url": normalized_href},
                    )
                )
            else:
                clean_url = normalized_href.split("#", maxsplit=1)[0]
                signals.append(
                    ExtractedSignal(
                        type="whatsapp_or_phone",
                        value=clean_url,
                        normalized_value=clean_url.lower(),
                        extraction_method="html_anchor",
                        details={"whatsapp_url": clean_url},
                    )
                )
    return signals


def _telegram_handle_from_url(raw_url: str) -> str | None:
    parsed = urlsplit(raw_url.strip())
    host = (parsed.hostname or "").lower()
    candidate: str | None = None
    if host in _TELEGRAM_HOSTS:
        candidate = parsed.path.strip("/").split("/", maxsplit=1)[0]
    elif parsed.scheme == "tg" and parsed.netloc.lower() == "resolve":
        candidate = parse_qs(parsed.query).get("domain", [""])[0]
    if candidate and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{4,31}", candidate):
        return candidate
    return None


def _phone_from_whatsapp_url(url: str) -> str | None:
    parsed = urlsplit(url)
    query_phone = parse_qs(parsed.query).get("phone", [""])[0]
    path_phone = parsed.path.strip("/").split("/", maxsplit=1)[0]
    raw_phone = query_phone or path_phone
    digits = re.sub(r"\D", "", raw_phone)
    return digits if 6 <= len(digits) <= 15 else None
