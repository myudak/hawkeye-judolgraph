"""Deterministic tests for captured-page outcome classification."""

from __future__ import annotations

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from hawkeye.classification import classify_capture
from hawkeye.models import CaptureOutcome


def _fixture_content(name: str) -> tuple[str, str]:
    html = (Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    return soup.title.get_text(" ", strip=True), soup.get_text(" ", strip=True)


@pytest.mark.parametrize(
    ("fixture_name", "expected_outcome", "expected_usable"),
    [
        ("normal_content.html", CaptureOutcome.CONTENT, True),
        ("unavailable_page.html", CaptureOutcome.UNAVAILABLE_PAGE, False),
        ("bot_challenge.html", CaptureOutcome.BOT_CHALLENGE, False),
        ("consent_wall.html", CaptureOutcome.CONSENT_WALL, False),
    ],
)
def test_classifies_required_fixture_categories(
    fixture_name: str, expected_outcome: CaptureOutcome, expected_usable: bool
) -> None:
    title, visible_text = _fixture_content(fixture_name)

    classification = classify_capture(
        title=title,
        final_url="https://fixture.test/",
        visible_text=visible_text,
        navigation_status="captured",
    )

    assert classification.outcome is expected_outcome
    assert classification.content_usable is expected_usable
    assert bool(classification.reasons) is not expected_usable


def test_classifies_geo_restriction_and_unknown_interstitial() -> None:
    geo = classify_capture(
        title="Regional availability",
        final_url="https://fixture.test/",
        visible_text="This service is not available in your country due to jurisdiction rules.",
        navigation_status="captured",
    )
    unknown = classify_capture(
        title="Request status",
        final_url="https://fixture.test/",
        visible_text="Access denied. Your request has been blocked by this service.",
        navigation_status="captured",
    )

    assert geo.outcome is CaptureOutcome.GEO_RESTRICTED
    assert unknown.outcome is CaptureOutcome.UNKNOWN_RESTRICTION


def test_timeout_and_navigation_error_take_precedence() -> None:
    timed_out = classify_capture(
        title="Just a moment...",
        final_url="https://fixture.test/",
        visible_text="Checking your browser",
        navigation_status="timed_out",
        error_type="TimeoutError",
    )
    failed = classify_capture(
        title="Just a moment...",
        final_url="https://fixture.test/",
        visible_text="Checking your browser",
        navigation_status="failed",
        error_type="ConnectionError",
    )

    assert timed_out.outcome is CaptureOutcome.TIMEOUT
    assert failed.outcome is CaptureOutcome.NAVIGATION_ERROR


def test_normal_cookie_banner_and_cloudflare_mention_are_not_false_restrictions() -> None:
    visible_text = """
        Welcome to our public information service. This page contains product details, guides,
        frequently asked questions, contact information, and a full explanation of our service.
        We use Cloudflare for network security. Cookie preferences are available and you may accept
        all cookies or reject non-essential cookies at any time from the footer.
    """

    classification = classify_capture(
        title="Public service information",
        final_url="https://fixture.test/",
        visible_text=visible_text,
        navigation_status="captured",
    )

    assert classification.outcome is CaptureOutcome.CONTENT
    assert classification.content_usable is True


def test_bot_challenge_url_marker_is_deterministic() -> None:
    first = classify_capture(
        title="Welcome",
        final_url="https://fixture.test/?__cf_chl_rt_tk=token",
        visible_text="Welcome to the site.",
        navigation_status="captured",
    )
    second = classify_capture(
        title="Welcome",
        final_url="https://fixture.test/?__cf_chl_rt_tk=token",
        visible_text="Welcome to the site.",
        navigation_status="captured",
    )

    assert first.outcome is CaptureOutcome.BOT_CHALLENGE
    assert first.model_dump() == second.model_dump()
