"""Isolated, bounded adapter for urlscan.io's public website-search endpoint."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from hawkeye.candidates.normalization import candidate_target_from_hostname
from hawkeye.collector.safety import SafetyPolicy, UnsafeUrlError

SOURCE_NAME: Literal["urlscan_public"] = "urlscan_public"
SOURCE_VERSION: Literal["urlscan-public-search-1"] = "urlscan-public-search-1"
SEARCH_ENDPOINT = "https://urlscan.io/api/v1/search/"
TRUSTED_ENDPOINT_HOST = "urlscan.io"
MAX_RESULT_LIMIT = 20
MAX_TIMEOUT_SECONDS = 10.0
MAX_RESPONSE_BYTES = 1_000_000
DEFAULT_USER_AGENT = "JudolGraph-HAWKEYE/0.4"

UrlscanTransport = Callable[[str, Mapping[str, str], float, int], bytes]


class ExternalDiscoverySourceError(ValueError):
    """Raised when one isolated external source cannot be queried safely or parsed."""


@dataclass(frozen=True)
class UrlscanSearchResponse:
    """One bounded raw source response plus its validated, locally usable result rows."""

    request_url: str
    raw_response: bytes
    results: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]
    collected_at: datetime
    collection_mode: Literal["live", "fixture_replay"]
    http_status: int | None


class ExternalDiscoverySource(Protocol):
    """Strategy contract for one bounded public source; V0.4 invokes one source at a time."""

    name: Literal["urlscan_public"]
    version: Literal["urlscan-public-search-1"]

    def collect(
        self, query_hostname: str, *, limit: int, timeout_seconds: float
    ) -> UrlscanSearchResponse:
        """Return one bounded response without navigating to source result URLs."""


class _BlockRedirects(HTTPRedirectHandler):
    """External discovery must not follow a source redirect to an arbitrary destination."""

    def redirect_request(
        self,
        request: Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        new_url: str,
    ) -> None:
        return None


class UrlscanPublicSearchSource:
    """Search existing public urlscan.io records for one completed case hostname.

    This adapter never submits a new scan and never navigates to URLs returned by urlscan.io. The
    optional fixture replay path exists only for deterministic automated tests and local review.
    """

    name: Literal["urlscan_public"] = SOURCE_NAME
    version: Literal["urlscan-public-search-1"] = SOURCE_VERSION

    def __init__(
        self,
        *,
        api_key: str | None = None,
        response_file: Path | str | None = None,
        transport: UrlscanTransport | None = None,
        safety_policy: SafetyPolicy | None = None,
    ) -> None:
        if api_key is not None and not api_key.strip():
            raise ValueError("urlscan API key must not be empty when provided")
        if response_file is not None and transport is not None:
            raise ValueError("response_file and transport are mutually exclusive")
        self._api_key = api_key
        self._response_file = Path(response_file) if response_file is not None else None
        self._transport = transport
        self._safety = safety_policy or SafetyPolicy()

    def collect(
        self, query_hostname: str, *, limit: int, timeout_seconds: float
    ) -> UrlscanSearchResponse:
        """Issue one bounded source request or replay one bounded JSON fixture."""

        _validate_collection_limits(limit=limit, timeout_seconds=timeout_seconds)
        target, exclusion_reason = candidate_target_from_hostname(query_hostname)
        if target is None:
            raise ExternalDiscoverySourceError(
                f"Source query hostname is not a public registrable hostname: {exclusion_reason}"
            )
        request_url = _request_url(target.hostname, limit)
        _validate_endpoint_contract(request_url)
        headers = _headers(self._api_key)
        if self._response_file is not None:
            raw_response = _read_fixture_response(self._response_file)
            collection_mode: Literal["live", "fixture_replay"] = "fixture_replay"
            http_status: int | None = None
        elif self._transport is not None:
            raw_response = self._transport(
                request_url, headers, timeout_seconds, MAX_RESPONSE_BYTES
            )
            collection_mode = "live"
            http_status = None
        else:
            try:
                self._safety.validate_url(request_url, refresh_dns=True)
            except UnsafeUrlError as error:
                raise ExternalDiscoverySourceError(
                    f"External source endpoint failed public-destination validation: {error}"
                ) from error
            raw_response = _bounded_json_get(request_url, headers, timeout_seconds)
            collection_mode = "live"
            http_status = 200
        if len(raw_response) > MAX_RESPONSE_BYTES:
            raise ExternalDiscoverySourceError("External source response exceeds byte limit")
        response_results, warnings = _parse_results(raw_response, limit)
        return UrlscanSearchResponse(
            request_url=request_url,
            raw_response=raw_response,
            results=response_results,
            warnings=warnings,
            collected_at=datetime.now(UTC),
            collection_mode=collection_mode,
            http_status=http_status,
        )


def _validate_collection_limits(*, limit: int, timeout_seconds: float) -> None:
    if not 1 <= limit <= MAX_RESULT_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_RESULT_LIMIT}")
    if not 0 < timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise ValueError(f"timeout_seconds must be between 0 and {MAX_TIMEOUT_SECONDS}")


def _request_url(hostname: str, limit: int) -> str:
    query = urlencode({"q": f"page.domain:{hostname}", "size": str(limit)})
    return f"{SEARCH_ENDPOINT}?{query}"


def _validate_endpoint_contract(request_url: str) -> None:
    """Keep every live request pinned to the one documented HTTPS endpoint contract."""

    try:
        parsed = urlsplit(request_url)
        port = parsed.port
    except ValueError as error:
        raise ExternalDiscoverySourceError(
            "External source endpoint contract is malformed"
        ) from error
    if (
        parsed.scheme != "https"
        or parsed.hostname != TRUSTED_ENDPOINT_HOST
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ExternalDiscoverySourceError("External source endpoint contract was rejected")


def _headers(api_key: str | None) -> dict[str, str]:
    headers = {"Accept": "application/json", "User-Agent": DEFAULT_USER_AGENT}
    if api_key is not None:
        headers["API-Key"] = api_key
    return headers


def _read_fixture_response(path: Path) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            raise ExternalDiscoverySourceError(
                f"External discovery fixture is not a regular file: {path}"
            )
        content = path.read_bytes()
    except OSError as error:
        raise ExternalDiscoverySourceError(
            f"Unable to read external discovery fixture: {path}"
        ) from error
    if len(content) > MAX_RESPONSE_BYTES:
        raise ExternalDiscoverySourceError("External discovery fixture exceeds byte limit")
    return content


def _bounded_json_get(
    request_url: str, headers: Mapping[str, str], timeout_seconds: float
) -> bytes:
    request = Request(request_url, headers=dict(headers), method="GET")
    opener = build_opener(ProxyHandler({}), _BlockRedirects())
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            status = response.getcode()
            if status != 200:
                raise ExternalDiscoverySourceError(f"External source returned HTTP {status}")
            content_type = response.headers.get_content_type()
            if content_type != "application/json":
                raise ExternalDiscoverySourceError(
                    f"External source returned unexpected content type: {content_type}"
                )
            declared_length = response.headers.get("Content-Length")
            if declared_length is not None:
                try:
                    if int(declared_length) > MAX_RESPONSE_BYTES:
                        raise ExternalDiscoverySourceError(
                            "External source response exceeds byte limit"
                        )
                except ValueError as error:
                    raise ExternalDiscoverySourceError(
                        "External source returned an invalid Content-Length"
                    ) from error
            content = bytes(response.read(MAX_RESPONSE_BYTES + 1))
    except ExternalDiscoverySourceError:
        raise
    except HTTPError as error:
        if 300 <= error.code < 400:
            raise ExternalDiscoverySourceError(
                f"External source redirect was blocked: HTTP {error.code}"
            ) from error
        raise ExternalDiscoverySourceError(f"External source returned HTTP {error.code}") from error
    except URLError as error:
        raise ExternalDiscoverySourceError(
            f"External source request failed: {error.reason}"
        ) from error
    if len(content) > MAX_RESPONSE_BYTES:
        raise ExternalDiscoverySourceError("External source response exceeds byte limit")
    return content


def _parse_results(
    raw_response: bytes, limit: int
) -> tuple[tuple[dict[str, Any], ...], tuple[str, ...]]:
    try:
        payload = json.loads(raw_response)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExternalDiscoverySourceError("External source response is not valid JSON") from error
    if not isinstance(payload, dict):
        raise ExternalDiscoverySourceError("External source JSON root must be an object")
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        raise ExternalDiscoverySourceError("External source response is missing a results list")
    warnings: list[str] = []
    if len(raw_results) > limit:
        warnings.append(
            f"source returned {len(raw_results)} rows; only the first {limit} rows were evaluated"
        )
    results: list[dict[str, Any]] = []
    ignored_rows = 0
    for item in raw_results[:limit]:
        if isinstance(item, dict):
            results.append(item)
        else:
            ignored_rows += 1
    if ignored_rows:
        warnings.append(f"ignored {ignored_rows} non-object source result rows")
    return tuple(results), tuple(warnings)
