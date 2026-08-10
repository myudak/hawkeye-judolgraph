"""Centralized Chromium launch policy for desktop and hardened container runtimes."""

from __future__ import annotations

import os

from playwright.sync_api import Browser, BrowserType


def launch_chromium(browser_type: BrowserType, *, headless: bool) -> Browser:
    """Launch Chromium with its sandbox enabled inside the prepared container boundary."""

    return browser_type.launch(
        headless=headless,
        chromium_sandbox=os.environ.get("HAWKEYE_CONTAINER") == "1",
    )
