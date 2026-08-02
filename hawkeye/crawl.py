"""Deterministic, bounded URL discovery helpers for Engine V0.1."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import SplitResult, parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

MAX_CRAWL_DEPTH = 1
MAX_CRAWL_PAGES = 5
MAX_CASE_TIMEOUT_SECONDS = 120.0
MAX_PAGE_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_HTML_BYTES = 5_000_000
TRACKING_PARAMETER_NAMES = frozenset({"fbclid", "gclid"})


@dataclass(frozen=True)
class DiscoveredLink:
    """One anchor occurrence, retaining source text alongside its crawl identity URL."""

    original_href: str
    normalized_url: str | None
    anchor_text: str


def normalize_crawl_url(raw_url: str, base_url: str) -> str | None:
    """Resolve and normalize one HTTP(S) crawl target without discarding material queries.

    The normalized representation is deliberately a crawl identity, not a replacement for raw
    evidence: it lowercases scheme/host, uses ASCII IDN hostnames, drops fragments/default ports,
    removes documented tracking keys, sorts the remaining query pairs, and removes a non-root
    trailing slash. Arbitrary query parameters stay intact because they can identify a real page.
    """

    raw = raw_url.strip()
    if not raw:
        return None
    resolved = urljoin(base_url, raw)
    try:
        parsed = urlsplit(resolved)
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None

    try:
        hostname = parsed.hostname.rstrip(".").casefold().encode("idna").decode("ascii")
    except UnicodeError:
        return None
    scheme = parsed.scheme.casefold()
    default_port = 443 if scheme == "https" else 80
    host_display = f"[{hostname}]" if ":" in hostname else hostname
    netloc = host_display if port in (None, default_port) else f"{host_display}:{port}"
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not _is_tracking_parameter(key)
    ]
    query = urlencode(sorted(query_pairs), doseq=True)
    return urlunsplit(SplitResult(scheme, netloc, path, query, ""))


def crawl_hostname(url: str) -> str | None:
    """Return the canonical hostname from a normalized crawl URL."""

    try:
        hostname = urlsplit(url).hostname
    except ValueError:
        return None
    if not hostname:
        return None
    try:
        return hostname.rstrip(".").casefold().encode("idna").decode("ascii")
    except UnicodeError:
        return None


def discover_anchor_links(html: str, base_url: str) -> list[DiscoveredLink]:
    """Read anchors in document order; callers apply safety/scope and sorted BFS policy."""

    soup = BeautifulSoup(html, "html.parser")
    discovered: list[DiscoveredLink] = []
    for anchor in soup.select("a[href]"):
        href = anchor.get("href")
        if not isinstance(href, str):
            continue
        discovered.append(
            DiscoveredLink(
                original_href=href,
                normalized_url=normalize_crawl_url(href, base_url),
                anchor_text=" ".join(anchor.get_text(" ", strip=True).split()),
            )
        )
    return discovered


def _is_tracking_parameter(key: str) -> bool:
    lowered = key.casefold()
    return lowered.startswith("utm_") or lowered in TRACKING_PARAMETER_NAMES
