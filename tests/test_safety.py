"""Unit coverage for public-only URL and redirect safety policy."""

from __future__ import annotations

import socket
import time

import pytest

from hawkeye.collector.safety import SafetyPolicy, UnsafeUrlError, resolve_dns


def public_resolver(_host: str, _port: int) -> list[str]:
    return ["93.184.216.34"]


def test_accepts_http_and_https_and_normalizes() -> None:
    policy = SafetyPolicy(resolver=public_resolver)

    http = policy.validate_url("HTTP://Example.TEST:80/path#fragment")
    https = policy.validate_url("https://example.test:443")

    assert http.normalized_url == "http://example.test/path"
    assert https.normalized_url == "https://example.test/"


def test_mocked_public_dns_destination_is_allowed() -> None:
    policy = SafetyPolicy(resolver=lambda _host, _port: ["93.184.216.34"])

    validated = policy.validate_url("https://public-fixture.test/path")

    assert validated.resolved_addresses == ("93.184.216.34",)


@pytest.mark.parametrize("url", ["file:///tmp/a", "ftp://example.test", "javascript:alert(1)"])
def test_rejects_unsupported_schemes(url: str) -> None:
    with pytest.raises(UnsafeUrlError, match="Only http"):
        SafetyPolicy(resolver=public_resolver).validate_url(url)


def test_rejects_localhost_before_navigation() -> None:
    with pytest.raises(UnsafeUrlError, match="Localhost"):
        SafetyPolicy(resolver=public_resolver).validate_url("http://localhost:8000")


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.1", "172.16.0.1", "192.168.1.1", "169.254.169.254"],
)
def test_rejects_private_ipv4_destinations(address: str) -> None:
    policy = SafetyPolicy(resolver=lambda _host, _port: [address])

    with pytest.raises(UnsafeUrlError, match="Non-public"):
        policy.validate_url("https://target.test")


@pytest.mark.parametrize("address", ["::1", "fc00::1", "fe80::1"])
def test_rejects_loopback_private_and_link_local_ipv6(address: str) -> None:
    policy = SafetyPolicy(resolver=lambda _host, _port: [address])

    with pytest.raises(UnsafeUrlError, match="Non-public"):
        policy.validate_url("https://target.test")


def test_rejects_cloud_metadata_host() -> None:
    with pytest.raises(UnsafeUrlError, match="Cloud metadata"):
        SafetyPolicy(resolver=public_resolver).validate_url("http://metadata.google.internal")


def test_revalidates_each_redirect_target() -> None:
    def resolver(host: str, _port: int) -> list[str]:
        return ["93.184.216.34"] if host == "public.test" else ["10.1.2.3"]

    policy = SafetyPolicy(resolver=resolver)
    assert policy.validate_url("https://public.test").hostname == "public.test"
    with pytest.raises(UnsafeUrlError, match="Non-public"):
        policy.validate_redirect_target("https://private-redirect.test")


def test_refresh_dns_rechecks_a_browser_request_instead_of_using_cached_answer() -> None:
    calls: list[tuple[str, int]] = []

    def resolver(host: str, port: int) -> list[str]:
        calls.append((host, port))
        return ["93.184.216.34"]

    policy = SafetyPolicy(resolver=resolver)
    policy.validate_url("https://public.test/resource")
    policy.validate_url("https://public.test/resource", refresh_dns=True)

    assert calls == [("public.test", 443), ("public.test", 443)]


def test_rejects_non_default_public_ports_for_crawl_navigation() -> None:
    policy = SafetyPolicy(resolver=public_resolver)

    with pytest.raises(UnsafeUrlError, match="Non-default ports"):
        policy.validate_crawl_url("https://public.test:8443/path")


def test_loopback_fixture_policy_can_use_a_custom_local_port_only() -> None:
    policy = SafetyPolicy(
        resolver=lambda _host, _port: ["127.0.0.1"], allow_loopback_for_testing=True
    )

    validated = policy.validate_crawl_url("http://127.0.0.1:8123/fixture")

    assert validated.port == 8123


def test_default_dns_resolution_has_a_hard_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def slow_getaddrinfo(*_args: object, **_kwargs: object) -> list[object]:
        time.sleep(0.2)
        return []

    monkeypatch.setattr(socket, "getaddrinfo", slow_getaddrinfo)

    with pytest.raises(UnsafeUrlError, match="DNS resolution timed out"):
        resolve_dns("slow.fixture.test", 443, timeout_seconds=0.01)


def test_loopback_override_is_narrowly_limited_to_test_fixtures() -> None:
    policy = SafetyPolicy(
        resolver=lambda _host, _port: ["127.0.0.1"], allow_loopback_for_testing=True
    )
    assert policy.validate_url("http://127.0.0.1:8123/").hostname == "127.0.0.1"

    private_policy = SafetyPolicy(
        resolver=lambda _host, _port: ["192.168.1.1"], allow_loopback_for_testing=True
    )
    with pytest.raises(UnsafeUrlError, match="Non-public"):
        private_policy.validate_url("http://fixture.test")
