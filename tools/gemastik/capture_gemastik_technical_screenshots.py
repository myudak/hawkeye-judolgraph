"""Capture current React UI screenshots from sanitized local fixtures only.

The script expects ``hawkeye app`` to be running against a data root created by
``hawkeye demo``. It creates two controlled ``.invalid`` fixture runs through
the localhost API, never contacts a public site, and records hashes for every
captured image.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright

VIEWPORT = {"width": 1440, "height": 1000}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_commit(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _capture(page: Page, destination: Path, description: str) -> dict[str, Any]:
    page.screenshot(path=str(destination), full_page=False)
    return {
        "file": destination.name,
        "description": description,
        "bytes": destination.stat().st_size,
        "sha256": _sha256(destination),
        "url": page.url,
    }


def _create_fixture_run(page: Page, scenario_id: str) -> str:
    result = page.evaluate(
        """async (scenarioId) => {
          const response = await fetch('/api/mvp/runs', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
              scenario_id: scenarioId,
              collection_mode: 'synthetic_fixture'
            })
          });
          return {status: response.status, body: await response.json()};
        }""",
        scenario_id,
    )
    if result["status"] != 200:
        raise RuntimeError(f"Fixture run failed for {scenario_id}: {result}")
    workspace_id = result["body"].get("workspace_id")
    if not isinstance(workspace_id, str) or not workspace_id:
        raise RuntimeError(f"Fixture run returned no workspace_id: {result}")
    return workspace_id


def capture(base_url: str, output_dir: Path, root: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    screenshots: list[dict[str, Any]] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT, device_scale_factor=1)
        page = context.new_page()

        page.goto(base_url, wait_until="networkidle")
        page.get_by_role("heading", name="Capture a public evidence trail").wait_for()
        page.get_by_role("button", name="Ganti ke Bahasa Indonesia").click()
        page.get_by_role("heading", name="Tangkap jejak bukti publik").wait_for()
        screenshots.append(
            _capture(
                page,
                output_dir / "01-beranda-kasus.png",
                "Beranda React dengan formulir investigasi dan kasus fixture terverifikasi.",
            )
        )

        redirect_workspace = _create_fixture_run(page, "redirect-new-tab")
        policy_workspace = _create_fixture_run(page, "login-register-distractors")

        page.goto(
            f"{base_url.rstrip('/')}/#/workspace/run/{redirect_workspace}",
            wait_until="networkidle",
        )
        page.locator(".workspace-command-bar").wait_for()
        page.locator(".graph-panel").wait_for()
        page.wait_for_timeout(900)
        screenshots.append(
            _capture(
                page,
                output_dir / "02-workspace-graf-bukti.png",
                "Workspace graf berbasis event untuk fixture redirect/new-tab.",
            )
        )

        page.locator('[role="tab"]').filter(has_text="Bukti").click()
        page.locator(".evidence-catalog-section").wait_for()
        screenshots.append(
            _capture(
                page,
                output_dir / "03-bukti-dan-review.png",
                "Panel bukti, klaim kandidat, dan formulir review append-only.",
            )
        )

        page.locator('[role="tab"]').filter(has_text="Teknis").click()
        page.get_by_role("heading", name="Bounded runtime").wait_for()
        screenshots.append(
            _capture(
                page,
                output_dir / "04-batas-teknis.png",
                "Panel batas teknis runtime dan jumlah event tersimpan.",
            )
        )

        page.goto(
            f"{base_url.rstrip('/')}/#/workspace/run/{policy_workspace}",
            wait_until="networkidle",
        )
        page.locator(".workspace-command-bar").wait_for()
        blocked = page.get_by_role("button", name="2 unsafe controls blocked", exact=False)
        blocked.wait_for()
        blocked.click()
        page.locator('[role="tab"]').filter(has_text="Bukti").click()
        page.get_by_role("heading", name="Persisted event").wait_for()
        screenshots.append(
            _capture(
                page,
                output_dir / "05-preflight-kebijakan.png",
                "Event preflight kebijakan: dua kontrol tidak aman diblokir tanpa eksekusi.",
            )
        )

        page.goto(
            f"{base_url.rstrip('/')}/#/summary/run/{redirect_workspace}",
            wait_until="networkidle",
        )
        page.get_by_role("heading", name="Investigation summary").wait_for()
        screenshots.append(
            _capture(
                page,
                output_dir / "06-ringkasan-dan-ekspor.png",
                "Ringkasan investigasi yang dapat dicetak dan diekspor.",
            )
        )

        context.close()
        browser.close()

    manifest = {
        "captured_at": datetime.now(UTC).isoformat(),
        "source": base_url,
        "source_commit": _git_commit(root),
        "fixture_boundary": "hawkeye demo plus controlled .invalid fixture runs; no public URL",
        "viewport": VIEWPORT,
        "workspaces": {
            "redirect": redirect_workspace,
            "policy": policy_workspace,
        },
        "screenshots": screenshots,
    }
    (output_dir / "screenshot-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8890")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("competition/gemastik-2026/assets/technical-current"),
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    manifest = capture(args.url, args.output, root)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
