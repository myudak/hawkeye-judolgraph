"""URL normalization and anchor-link extraction."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import SplitResult, parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class LinkRecord:
    """One normalized public HTTP(S) anchor link."""

    url: str
    hostname: str
    kind: str
    anchor_text: str
    rel: str
    source_region: str


def normalize_http_url(raw_url: str, base_url: str) -> str | None:
    """Resolve a relative URL, retain HTTP(S), and remove its fragment."""

    raw = raw_url.strip()
    if not raw:
        return None
    resolved = urljoin(base_url, raw)
    try:
        parsed = urlsplit(resolved)
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return None

    hostname = parsed.hostname.rstrip(".").lower()
    try:
        hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError:
        return None

    default_port = 443 if parsed.scheme.lower() == "https" else 80
    displayed_host = f"[{hostname}]" if ":" in hostname else hostname
    netloc = displayed_host if port in (None, default_port) else f"{displayed_host}:{port}"
    normalized = SplitResult(
        scheme=parsed.scheme.lower(),
        netloc=netloc,
        path=parsed.path or "/",
        query=parsed.query,
        fragment="",
    )
    return urlunsplit(normalized)


def normalize_exact_asset_url(raw_url: str, base_url: str) -> tuple[str, str] | None:
    """Return observed and query-canonical forms of an exact passive asset URL.

    Query keys and values are retained verbatim (apart from standard URL encoding), because they
    can identify different tenant-specific assets or signed resources. Sorting only removes
    irrelevant parameter ordering differences; it never drops arbitrary parameters.
    """

    observed_url = normalize_http_url(raw_url, base_url)
    if observed_url is None:
        return None
    try:
        parsed = urlsplit(observed_url)
    except ValueError:
        return None
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)), doseq=True)
    canonical_url = urlunsplit(SplitResult(parsed.scheme, parsed.netloc, parsed.path, query, ""))
    return observed_url, canonical_url


def hostname_from_url(url: str) -> str | None:
    """Return a normalized hostname for an already-normalized HTTP(S) URL."""

    try:
        hostname = urlsplit(url).hostname
    except ValueError:
        return None
    return hostname.rstrip(".").lower() if hostname else None


def extract_anchor_links(soup: BeautifulSoup, base_url: str) -> list[LinkRecord]:
    """Extract normalized links and classify each by its host relative to the page."""

    base_hostname = hostname_from_url(base_url)
    records: list[LinkRecord] = []
    for anchor in soup.select("a[href]"):
        href = anchor.get("href")
        if not isinstance(href, str):
            continue
        normalized = normalize_http_url(href, base_url)
        if normalized is None:
            continue
        hostname = hostname_from_url(normalized)
        if hostname is None:
            continue
        kind = "internal_link" if hostname == base_hostname else "external_link"
        rel = anchor.get("rel", [])
        rel_values = (
            [str(value).casefold() for value in rel] if isinstance(rel, list) else [str(rel)]
        )
        region = anchor.find_parent(["footer", "header", "nav", "main", "aside"])
        records.append(
            LinkRecord(
                url=normalized,
                hostname=hostname,
                kind=kind,
                anchor_text=" ".join(anchor.get_text(" ", strip=True).split()),
                rel=" ".join(sorted(value for value in rel_values if value)),
                source_region=region.name if region is not None else "document",
            )
        )
    return records
