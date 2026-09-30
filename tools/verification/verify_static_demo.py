from __future__ import annotations

import functools
import json
import re
import shutil
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Page, Route, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "apps/web/dist-demo"
OUTPUT = ROOT / "verification-output/static-demo"


class StaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


def main() -> None:
    if not (BUILD / "index.html").is_file():
        raise RuntimeError("Build the static demo first with pnpm build:demo.")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    violations: list[str] = []
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="hawkeye-static-demo-") as temporary:
        shutil.copytree(BUILD, Path(temporary) / "hawkeye-demo")
        handler = functools.partial(StaticHandler, directory=temporary)
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f"http://127.0.0.1:{server.server_port}"
        base = f"{origin}/hawkeye-demo/"

        def restrict(route: Route) -> None:
            url = urlparse(route.request.url)
            if url.scheme in {"data", "blob"}:
                route.continue_()
            elif f"{url.scheme}://{url.netloc}" != origin or "/api/" in url.path:
                violations.append(route.request.url)
                route.abort()
            elif not url.path.startswith("/hawkeye-demo/"):
                violations.append(route.request.url)
                route.abort()
            else:
                route.continue_()

        def check_images(page: Page) -> None:
            page.wait_for_function("Array.from(document.images).every(image => image.complete)")
            broken = page.locator("img").evaluate_all(
                "images => images.filter(image => !image.naturalWidth).map(image => image.src)"
            )
            assert not broken, f"Broken bundled images: {broken}"

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                context = browser.new_context(viewport={"width": 1440, "height": 1000})
                context.route("**/*", restrict)
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base, wait_until="networkidle")
                expect(page.get_by_role("heading", name="Explore an investigation")).to_be_visible()
                expect(page.locator('input[type="url"]')).to_have_count(0)
                expect(page.get_by_text("Demo · Sample data", exact=True)).to_be_visible()
                check_images(page)
                page.screenshot(path=str(OUTPUT / "landing.png"), full_page=True)

                for scenario, title in (
                    ("demo-contact", "Public contact trail"),
                    ("demo-related", "Related-site review"),
                    ("demo-restricted", "Limited capture"),
                ):
                    page.goto(base, wait_until="networkidle")
                    page.get_by_role("combobox", name="Sample scenario").click()
                    page.get_by_role("option", name=title, exact=True).click()
                    page.get_by_role("button", name="Start demo", exact=True).click()
                    page.wait_for_url(f"**/#/scan/{scenario}")
                    expect(
                        page.get_by_text("Accelerated sample playback.", exact=False)
                    ).to_be_visible()
                    page.reload(wait_until="networkidle")
                    page.locator(".open-workspace-button").wait_for(timeout=15000)
                    page.locator(".open-workspace-button").click()
                    page.wait_for_url(f"**/#/workspace/run/{scenario}")
                    expect(page.get_by_role("region", name="Demo guide")).to_be_visible()
                    page.get_by_role("button", name="Start timeline", exact=True).click()
                    expect(page.locator(".timeline-current")).to_contain_text("01/")
                    page.get_by_role("button", name="Next", exact=True).click()
                    page.get_by_role("button", name="Open evidence", exact=True).click()
                    expect(page.get_by_role("tab", name="Evidence", exact=True)).to_have_attribute(
                        "aria-selected", "true"
                    )
                    check_images(page)
                    if scenario == "demo-contact":
                        expect(page.locator(".screenshot-gallery img")).to_have_attribute(
                            "src", re.compile("demo-contact-case-page-2")
                        )
                    if scenario == "demo-related":
                        page.get_by_role("button", name="Reveal sample candidate page").click()
                        page.get_by_label("Reviewer label").fill("Demo reviewer")
                        page.get_by_label("Evidence-bounded reason").fill(
                            "The sample source page visibly links to Harbor; ownership is unknown."
                        )
                        page.get_by_role("button", name="Save demo review").click()
                        expect(
                            page.get_by_text("Demo review saved for this session")
                        ).to_be_visible()
                        page.reload(wait_until="networkidle")
                        page.get_by_role("tab", name="Evidence", exact=True).click()
                        expect(
                            page.get_by_role("button", name="Reveal sample candidate page")
                        ).to_have_count(0)
                    if scenario == "demo-restricted":
                        expect(page.locator(".review-form")).to_have_count(0)
                    page.screenshot(path=str(OUTPUT / f"{scenario}.png"), full_page=True)
                    page.get_by_role("button", name="View summary", exact=True).click()
                    expect(
                        page.get_by_role("heading", name="Investigation summary")
                    ).to_be_visible()
                    expect(page.locator(".demo-report-note")).to_be_visible()
                    expect(page.get_by_text("Case archive", exact=True)).to_have_count(0)
                    with page.expect_download() as download:
                        page.get_by_role("link", name="JSON Structured case").click()
                    exported = json.loads(Path(download.value.path()).read_text())
                    assert exported["demo"] and exported["session_only"]
                    assert exported["run"]["workspace_id"] == scenario
                    if scenario == "demo-related":
                        assert exported["run"]["current_assertion_status"] == "verified"
                        assert len(exported["run"]["reviews"]) == 1
                    if scenario == "demo-restricted":
                        assert not exported["run"]["source_case"]["observations"]
                    with page.expect_download() as download:
                        page.get_by_role("link", name="Markdown .md report").click()
                    assert "synthetic" in Path(download.value.path()).read_text()

                page.get_by_role("button", name="Reset demo", exact=True).click()
                page.goto(f"{base}#/workspace/run/demo-related", wait_until="networkidle")
                page.get_by_role("tab", name="Evidence", exact=True).click()
                expect(
                    page.get_by_role("button", name="Reveal sample candidate page")
                ).to_be_visible()
                page.goto(f"{base}#/workspace/run/unknown", wait_until="networkidle")
                expect(
                    page.get_by_text("This demo only supports the supplied scenarios.")
                ).to_be_visible()

                for theme in ("dark", "light"):
                    page.goto(base, wait_until="networkidle")
                    page.get_by_role("button", name="Display theme", exact=True).click()
                    page.get_by_role("menuitem", name=theme.title(), exact=False).click()
                    check_images(page)
                    page.screenshot(path=str(OUTPUT / f"landing-{theme}.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                page.goto(base, wait_until="networkidle")
                page.get_by_role("button", name="Ganti ke Bahasa Indonesia").click()
                expect(
                    page.get_by_role("heading", name="Jelajahi alur investigasi")
                ).to_be_visible()
                expect(page.get_by_role("combobox", name="Skenario contoh")).to_be_visible()
                assert page.locator(".app-header button").evaluate_all(
                    "buttons => buttons.every(button => button.getBoundingClientRect().right "
                    "<= innerWidth && button.getBoundingClientRect().left >= 0)"
                )
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                check_images(page)
                page.screenshot(path=str(OUTPUT / "mobile-indonesian.png"), full_page=True)
                page.goto(f"{base}#/workspace/run/demo-contact", wait_until="networkidle")
                expect(page.get_by_role("region", name="Panduan demo")).to_be_visible()
                page.get_by_role("button", name="Lanjut", exact=True).click()
                page.get_by_role("button", name="Buka bukti", exact=True).click()
                check_images(page)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.screenshot(path=str(OUTPUT / "mobile-workspace.png"), full_page=True)
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    assert not violations, f"Demo attempted forbidden requests: {violations}"
    assert not errors, f"Browser errors: {errors}"
    print(
        "Static demo verified: three scenarios, reload, review/reset, exports, themes, mobile, "
        "subpath; zero API/external requests."
    )


if __name__ == "__main__":
    main()
