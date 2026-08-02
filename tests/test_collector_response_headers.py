"""Regression coverage for malformed real-browser response-header values."""

from __future__ import annotations

from typing import cast

from playwright.sync_api import Response

from hawkeye.collector.playwright_collector import _sanitized_response_headers


class _ResponseWithNullHeader:
    def all_headers(self) -> dict[str, object]:
        return {
            "Content-Type": "text/html; charset=utf-8",
            "ETag": None,
            "Set-Cookie": "must-not-be-persisted",
            "Server": "x" * 1200,
        }


def test_null_header_is_ignored_without_losing_safe_metadata() -> None:
    headers = _sanitized_response_headers(cast(Response, _ResponseWithNullHeader()))
    assert headers == {
        "content-type": "text/html; charset=utf-8",
        "server": "x" * 1000,
    }
