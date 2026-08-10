"""Exact-origin configuration for an explicitly enabled temporary public demo."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

_PUBLIC_DEMO_ORIGIN_ENV = "HAWKEYE_PUBLIC_DEMO_ORIGIN"
_PUBLIC_HOST_PATTERN = re.compile(
    r"(?=.{4,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
)


@dataclass(frozen=True)
class PublicDemoOrigin:
    """Canonical HTTPS origin and exact hostname permitted for a temporary demo."""

    origin: str
    hostname: str

    @classmethod
    def from_environment(cls) -> PublicDemoOrigin | None:
        raw_origin = os.environ.get(_PUBLIC_DEMO_ORIGIN_ENV, "").strip()
        if not raw_origin:
            return None

        parsed = urlsplit(raw_origin)
        try:
            port = parsed.port
        except ValueError as error:
            raise ValueError(_configuration_error()) from error
        hostname = parsed.hostname
        if (
            parsed.scheme.casefold() != "https"
            or hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or port not in {None, 443}
            or "*" in parsed.netloc
            or hostname.endswith(".")
        ):
            raise ValueError(_configuration_error())
        try:
            canonical_hostname = hostname.encode("idna").decode("ascii").casefold()
        except UnicodeError as error:
            raise ValueError(_configuration_error()) from error
        if _PUBLIC_HOST_PATTERN.fullmatch(canonical_hostname) is None:
            raise ValueError(_configuration_error())
        return cls(origin=f"https://{canonical_hostname}", hostname=canonical_hostname)


def _configuration_error() -> str:
    return (
        "HAWKEYE_PUBLIC_DEMO_ORIGIN must be one absolute default-port HTTPS origin "
        "without credentials, wildcard, trailing dot, path, query, or fragment"
    )
