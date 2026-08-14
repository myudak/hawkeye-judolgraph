"""URL and network-destination safety checks for public-page collection."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from threading import Event, Thread
from typing import Any
from urllib.parse import SplitResult, urlsplit, urlunsplit


class UnsafeUrlError(ValueError):
    """Raised when a URL is outside the public-only collection boundary."""


AddressResolver = Callable[[str, int], Sequence[str]]


def resolve_dns(hostname: str, port: int, *, timeout_seconds: float = 5.0) -> Sequence[str]:
    """Resolve every address within a hard wall-clock limit before safety checks.

    ``socket.getaddrinfo`` has no portable per-call timeout. The isolated daemon worker keeps a
    stuck platform resolver from blocking a bounded case; any late result is discarded.
    """

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    records: list[Any] | None = None
    resolution_error: OSError | None = None
    completed = Event()

    def resolve() -> None:
        nonlocal records, resolution_error
        try:
            records = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        except OSError as error:
            resolution_error = error
        finally:
            completed.set()

    worker = Thread(target=resolve, daemon=True)
    worker.start()
    if not completed.wait(timeout_seconds):
        raise UnsafeUrlError(f"DNS resolution timed out for {hostname}")
    if resolution_error is not None:
        raise UnsafeUrlError(
            f"DNS resolution failed for {hostname}: {resolution_error}"
        ) from resolution_error
    if records is None:
        raise UnsafeUrlError(f"DNS resolution returned no records for {hostname}")

    addresses: set[str] = set()
    for record in records:
        address = record[4][0]
        if isinstance(address, str):
            addresses.add(address)
    if not addresses:
        raise UnsafeUrlError(f"DNS resolution returned no addresses for {hostname}")
    return sorted(addresses)


@dataclass(frozen=True)
class ValidatedUrl:
    """A normalized URL with the DNS answers that were allowed."""

    normalized_url: str
    hostname: str
    port: int
    resolved_addresses: tuple[str, ...]


@dataclass
class SafetyPolicy:
    """Fail-closed validation for seed URLs, redirects, and browser requests.

    ``allow_loopback_for_testing`` is intentionally narrow: it permits only loopback
    destinations for deterministic local fixtures. It does not permit other private,
    link-local, or cloud-metadata destinations and defaults to ``False``.
    """

    resolver: AddressResolver | None = None
    dns_timeout_seconds: float = 5.0
    allow_loopback_for_testing: bool = False
    _cache: dict[tuple[str, int], tuple[str, ...]] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        if self.dns_timeout_seconds <= 0:
            raise ValueError("dns_timeout_seconds must be positive")

    def validate_url(self, raw_url: str, *, refresh_dns: bool = False) -> ValidatedUrl:
        """Normalize an HTTP(S) URL and fail if any DNS answer is non-public.

        Main-frame request interception passes ``refresh_dns=True`` so every browser navigation is
        checked again at dispatch time. Subresources resolve once per authority in the isolated,
        bounded browser context and then reuse this case-local cache; this avoids serializing
        hundreds of identical resolver calls while preserving the public-address check before the
        first dispatch to each authority.
        """

        parsed = self._parse_and_normalize(raw_url)
        hostname = self._canonical_hostname(parsed)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)

        if self._is_cloud_metadata_hostname(hostname):
            raise UnsafeUrlError(f"Cloud metadata host is not allowed: {hostname}")
        if self._is_localhost_name(hostname) and not self.allow_loopback_for_testing:
            raise UnsafeUrlError(f"Localhost is not allowed: {hostname}")

        addresses = self._resolve(hostname, port, refresh_dns=refresh_dns)
        for address in addresses:
            self._validate_address(address, hostname)

        return ValidatedUrl(
            normalized_url=self._normalized_url(parsed, hostname),
            hostname=hostname,
            port=port,
            resolved_addresses=addresses,
        )

    def validate_redirect_target(self, raw_url: str) -> ValidatedUrl:
        """Re-run the same public-destination checks for every redirect target."""

        return self.validate_url(raw_url)

    def validate_crawl_url(self, raw_url: str, *, refresh_dns: bool = False) -> ValidatedUrl:
        """Validate a top-level crawl document, including the narrow default-port policy.

        Public crawl navigation is restricted to HTTP port 80 and HTTPS port 443. A custom port is
        allowed only when every resolved destination is loopback and the explicit fixture policy is
        enabled, so local integration tests can exercise the real browser path without weakening
        public collection.
        """

        validated = self.validate_url(raw_url, refresh_dns=refresh_dns)
        default_port = 443 if validated.normalized_url.startswith("https://") else 80
        if validated.port == default_port:
            return validated
        if self.allow_loopback_for_testing and all(
            ipaddress.ip_address(address).is_loopback for address in validated.resolved_addresses
        ):
            return validated
        raise UnsafeUrlError(
            "Non-default ports are not allowed for public crawl navigation: "
            f"{validated.hostname}:{validated.port}"
        )

    def _resolve(self, hostname: str, port: int, *, refresh_dns: bool = False) -> tuple[str, ...]:
        cache_key = (hostname, port)
        if refresh_dns or cache_key not in self._cache:
            try:
                answers = tuple(
                    sorted(
                        set(
                            resolve_dns(
                                hostname,
                                port,
                                timeout_seconds=self.dns_timeout_seconds,
                            )
                            if self.resolver is None
                            else self.resolver(hostname, port)
                        )
                    )
                )
            except UnsafeUrlError:
                raise
            except OSError as error:
                raise UnsafeUrlError(f"DNS resolution failed for {hostname}: {error}") from error
            if not answers:
                raise UnsafeUrlError(f"DNS resolution returned no addresses for {hostname}")
            self._cache[cache_key] = answers
        return self._cache[cache_key]

    @staticmethod
    def _parse_and_normalize(raw_url: str) -> SplitResult:
        candidate = raw_url.strip()
        if not candidate:
            raise UnsafeUrlError("URL must not be empty")
        try:
            parsed = urlsplit(candidate)
            _ = parsed.port
        except ValueError as error:
            raise UnsafeUrlError(f"Invalid URL: {error}") from error
        if parsed.scheme.lower() not in {"http", "https"}:
            raise UnsafeUrlError("Only http:// and https:// URLs are allowed")
        if not parsed.hostname:
            raise UnsafeUrlError("URL must include a hostname")
        if parsed.username is not None or parsed.password is not None:
            raise UnsafeUrlError("URL userinfo is not allowed")
        return parsed

    @staticmethod
    def _canonical_hostname(parsed: SplitResult) -> str:
        assert parsed.hostname is not None
        raw_hostname = parsed.hostname.rstrip(".").lower()
        try:
            return raw_hostname.encode("idna").decode("ascii")
        except UnicodeError as error:
            raise UnsafeUrlError(f"Invalid hostname: {raw_hostname}") from error

    @staticmethod
    def _normalized_url(parsed: SplitResult, hostname: str) -> str:
        port = parsed.port
        default_port = 443 if parsed.scheme.lower() == "https" else 80
        host_display = f"[{hostname}]" if ":" in hostname else hostname
        netloc = host_display if port in (None, default_port) else f"{host_display}:{port}"
        return urlunsplit(
            (
                parsed.scheme.lower(),
                netloc,
                parsed.path or "/",
                parsed.query,
                "",
            )
        )

    @staticmethod
    def _is_localhost_name(hostname: str) -> bool:
        return (
            hostname == "localhost"
            or hostname.endswith(".localhost")
            or hostname == "localhost.localdomain"
        )

    @staticmethod
    def _is_cloud_metadata_hostname(hostname: str) -> bool:
        blocked = {
            "metadata",
            "metadata.google.internal",
            "metadata.google",
            "instance-data",
            "169.254.169.254",
            "fd00:ec2::254",
        }
        return hostname in blocked

    def _validate_address(self, raw_address: str, hostname: str) -> None:
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError as error:
            raise UnsafeUrlError(
                f"Resolver returned invalid address for {hostname}: {raw_address}"
            ) from error

        if address.is_loopback and self.allow_loopback_for_testing:
            return

        if not address.is_global:
            message = (
                "Non-public network destination is not allowed for "
                f"{hostname}: {address.compressed}"
            )
            raise UnsafeUrlError(message)
