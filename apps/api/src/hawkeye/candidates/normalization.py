"""Stable candidate-domain normalization without DNS lookups or network access."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

import tldextract


@dataclass(frozen=True)
class CandidateTarget:
    """A public registrable-domain identity and the exact observed hostname."""

    registrable_domain: str
    hostname: str
    suffix_type: Literal["icann", "private"]


# Empty suffix-list URLs makes the public-suffix parser fully local and deterministic. Candidate
# generation must never cause a network request merely to normalize an observed URL.
_EXTRACT = tldextract.TLDExtract(suffix_list_urls=(), include_psl_private_domains=True)

# Exact asset URLs from these shared providers are routinely common and do not, on their own,
# provide a useful candidate-domain lead. This deliberately targets infrastructure providers,
# not arbitrary domains that happen to use a "cdn" subdomain.
COMMON_ASSET_PROVIDER_SUFFIXES = frozenset(
    {
        "ajax.googleapis.com",
        "bootstrapcdn.com",
        "cdnjs.cloudflare.com",
        "cloudflare.com",
        "cloudflareinsights.com",
        "cloudfront.net",
        "doubleclick.net",
        "fonts.googleapis.com",
        "fonts.gstatic.com",
        "google-analytics.com",
        "googletagmanager.com",
        "gstatic.com",
        "hotjar.com",
        "jsdelivr.net",
        "sentry.io",
        "unpkg.com",
    }
)

# Direct links to ubiquitous service or reference destinations remain immutable excluded
# observations, but do not become high-noise investigation leads merely because a site has a
# standard footer, social-media, or contact link.
COMMON_EXTERNAL_REFERENCE_SUFFIXES = frozenset(
    {
        "facebook.com",
        "instagram.com",
        "linkedin.com",
        "t.me",
        "telegram.me",
        "twitter.com",
        "wa.me",
        "whatsapp.com",
        "x.com",
        "youtube.com",
    }
)
GENERIC_REFERRAL_VALUES = frozenset(
    {"", "0", "1", "code", "default", "none", "null", "ref", "test", "unknown"}
)


def candidate_target_from_url(raw_url: str) -> tuple[CandidateTarget | None, str | None]:
    """Return a candidate identity for one observed HTTP(S) URL, or an exclusion reason."""

    try:
        parsed = urlsplit(raw_url.strip())
        _ = parsed.port
    except ValueError:
        return None, "malformed_url"
    if parsed.scheme.casefold() not in {"http", "https"}:
        return None, "unsupported_url_scheme"
    if parsed.username is not None or parsed.password is not None:
        return None, "userinfo_not_allowed"
    if not parsed.hostname:
        return None, "missing_hostname"
    return candidate_target_from_hostname(parsed.hostname)


def candidate_target_from_hostname(raw_hostname: str) -> tuple[CandidateTarget | None, str | None]:
    """Normalize a hostname and require a non-IP registrable domain."""

    hostname = raw_hostname.strip().rstrip(".").casefold()
    if not hostname:
        return None, "missing_hostname"
    try:
        hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError:
        return None, "invalid_idn_hostname"
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        return None, "ip_literal_candidate"

    extracted = _EXTRACT(hostname)
    registrable_domain = extracted.top_domain_under_public_suffix
    if not registrable_domain:
        return None, "not_registrable_domain"
    return (
        CandidateTarget(
            registrable_domain=registrable_domain.casefold(),
            hostname=hostname,
            suffix_type="private" if extracted.is_private else "icann",
        ),
        None,
    )


def hostname_from_observed_url(raw_url: str) -> str | None:
    """Return an IDN-normalized hostname from an observed URL without candidate validation."""

    try:
        parsed = urlsplit(raw_url.strip())
        hostname = parsed.hostname
    except ValueError:
        return None
    if not hostname:
        return None
    try:
        return hostname.rstrip(".").casefold().encode("idna").decode("ascii")
    except UnicodeError:
        return None


def is_common_asset_provider(hostname: str | None) -> bool:
    """Return whether a hostname is an intentionally suppressed shared asset provider."""

    if hostname is None:
        return False
    normalized = hostname.rstrip(".").casefold()
    return any(
        normalized == suffix or normalized.endswith(f".{suffix}")
        for suffix in COMMON_ASSET_PROVIDER_SUFFIXES
    )


def is_common_external_reference(hostname: str | None) -> bool:
    """Return whether a direct anchor points to a ubiquitous non-candidate service host."""

    if hostname is None:
        return False
    normalized = hostname.rstrip(".").casefold()
    return any(
        normalized == suffix or normalized.endswith(f".{suffix}")
        for suffix in COMMON_EXTERNAL_REFERENCE_SUFFIXES
    )


def is_generic_referral_signal(value: str) -> bool:
    """Apply the V0.2 generic-referral suppression policy without altering the observed value."""

    _, separator, raw_value = value.partition("=")
    if not separator:
        return True
    normalized = raw_value.strip().casefold()
    return len(normalized) < 4 or normalized in GENERIC_REFERRAL_VALUES
