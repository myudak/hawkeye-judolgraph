"""Bounded, opt-in V0.4 adapters for independently auditable public discovery sources."""

from hawkeye.discovery.service import (
    ExternalDiscoveryInputError,
    ExternalDiscoveryResult,
    discover_case,
)
from hawkeye.discovery.urlscan import (
    ExternalDiscoverySource,
    ExternalDiscoverySourceError,
    UrlscanPublicSearchSource,
)

__all__ = [
    "ExternalDiscoveryInputError",
    "ExternalDiscoveryResult",
    "ExternalDiscoverySource",
    "ExternalDiscoverySourceError",
    "UrlscanPublicSearchSource",
    "discover_case",
]
