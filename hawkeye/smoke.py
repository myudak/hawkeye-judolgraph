"""Bounded live robustness matrix for Engine V0.1, with crawling disabled."""

from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from hawkeye.pipeline import investigate

LIVE_SMOKE_URLS = (
    "https://888.com",
    "https://888casino.com",
    "https://888poker.com",
    "https://888sport.com",
    "https://betfair.com",
    "https://paddypower.com",
    "https://skybet.com",
    "https://skyvegas.com",
    "https://bet365.com",
    "https://williamhill.com",
)


def run_live_smoke(output: Path | str) -> dict[str, Any]:
    """Run the fixed ten-domain matrix, preserving failures and continuing after each one."""

    root = Path(output).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    cases_root = root / "_case-artifacts"
    results: list[dict[str, Any]] = []
    for index, seed_url in enumerate(LIVE_SMOKE_URLS, start=1):
        results.append(_run_one(seed_url, root, cases_root, index))

    summary = {
        "matrix": "Engine V0.1 fixed ten-domain live smoke test",
        "limits": {
            "maximum_primary_pages_per_domain": 1,
            "maximum_crawl_depth": 0,
            "maximum_redirects": 5,
            "timeout_seconds_per_attempt": 30,
            "controlled_retries": 1,
            "fresh_browser_context_per_attempt": True,
        },
        "results": results,
        "success_count": sum(result["navigation_status"] == "captured" for result in results),
        "navigation_captured_count": sum(
            result["navigation_status"] == "captured" for result in results
        ),
        "usable_content_count": sum(result["content_usable"] for result in results),
        "outcome_counts": dict(
            sorted(Counter(result["capture_outcome"] for result in results).items())
        ),
        "navigation_failure_count": sum(
            result["navigation_status"] not in {"captured", "pending"} for result in results
        ),
        "failure_or_restriction_count": sum(not result["content_usable"] for result in results),
    }
    _write_json(root / "summary.json", summary)
    (root / "summary.md").write_text(_render_summary_markdown(results), encoding="utf-8")
    return summary


def _run_one(seed_url: str, root: Path, cases_root: Path, index: int) -> dict[str, Any]:
    hostname = urlsplit(seed_url).hostname or f"target-{index}"
    target_root = root / hostname
    target_root.mkdir(parents=True, exist_ok=True)
    attempts = 0
    total_duration = 0.0
    final_result: dict[str, Any] | None = None

    while attempts < 2:
        attempts += 1
        started = time.monotonic()
        case_id = f"smoke-{index:02d}-{hostname.replace('.', '-')}-attempt-{attempts}"
        try:
            result = investigate(
                seed_url,
                output=cases_root,
                case_id=case_id,
                timeout_seconds=30.0,
                case_timeout_seconds=30.0,
                max_pages=1,
                max_depth=0,
                max_redirects=5,
            )
        except Exception as error:
            duration = round(time.monotonic() - started, 3)
            final_result = _failed_summary(seed_url, str(error), duration)
        else:
            duration = round(time.monotonic() - started, 3)
            final_result = _summarize_case(
                seed_url,
                result.case_directory,
                result.case.model_dump(mode="json"),
                duration,
            )
        total_duration += duration
        final_result["attempts"] = attempts
        if final_result["navigation_result"] == "completed":
            break

    assert final_result is not None
    final_result["duration_seconds"] = round(total_duration, 3)
    case_directory = final_result.get("case_directory")
    artifact_paths = (
        _copy_primary_artifacts(Path(case_directory), target_root)
        if case_directory
        else _empty_artifact_paths()
    )
    final_result["artifact_paths"] = artifact_paths
    final_result.pop("case_directory", None)
    _write_json(target_root / "result.json", final_result)
    return final_result


def _failed_summary(seed_url: str, error: str, duration_seconds: float) -> dict[str, Any]:
    return {
        "input_domain": seed_url,
        "final_url": None,
        "navigation_result": "failed",
        "navigation_status": "failed",
        "capture_outcome": "navigation_error",
        "content_usable": False,
        "classification_reasons": ["navigation did not complete"],
        "redirect_count": 0,
        "page_title": None,
        "entity_counts": {},
        "screenshot_status": "unavailable",
        "duration_seconds": duration_seconds,
        "failure_or_restriction_reason": error,
        "case_directory": None,
    }


def _summarize_case(
    seed_url: str, case_directory: str, case: dict[str, Any], duration_seconds: float
) -> dict[str, Any]:
    directory = Path(case_directory)
    entities_path = directory / "entities.json"
    entities: list[dict[str, Any]] = []
    if entities_path.exists():
        entities = json.loads(entities_path.read_text(encoding="utf-8"))
    title = case.get("page_title") or next(
        (entity["value"] for entity in entities if entity["type"] == "page_title"), None
    )
    classification_reasons = case.get("classification_reasons", [])
    error_or_reason = case.get("error") or "; ".join(classification_reasons) or None
    return {
        "input_domain": seed_url,
        "final_url": case.get("final_url"),
        "navigation_result": case["status"],
        "navigation_status": case.get("navigation_status", "failed"),
        "capture_outcome": case.get("capture_outcome", "navigation_error"),
        "content_usable": case.get("content_usable") is True,
        "classification_reasons": classification_reasons,
        "redirect_count": len(case.get("redirect_chain", [])),
        "page_title": title,
        "entity_counts": dict(sorted(Counter(entity["type"] for entity in entities).items())),
        "screenshot_status": "captured"
        if (directory / "screenshots" / "page-001.png").exists()
        else "unavailable",
        "duration_seconds": duration_seconds,
        "failure_or_restriction_reason": error_or_reason,
        "case_directory": case_directory,
    }


def _copy_primary_artifacts(case_directory: Path, target_root: Path) -> dict[str, str | None]:
    html_source = case_directory / "pages" / "page-001.html"
    screenshot_source = case_directory / "screenshots" / "page-001.png"
    html_target = target_root / "page.html"
    screenshot_target = target_root / "screenshot.png"
    if html_source.exists():
        shutil.copy2(html_source, html_target)
    if screenshot_source.exists():
        shutil.copy2(screenshot_source, screenshot_target)
    return {
        "case": str(case_directory),
        "html": str(html_target) if html_target.exists() else None,
        "screenshot": str(screenshot_target) if screenshot_target.exists() else None,
    }


def _empty_artifact_paths() -> dict[str, None]:
    return {"case": None, "html": None, "screenshot": None}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        f"{json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)}\n",
        encoding="utf-8",
    )


def _render_summary_markdown(results: list[dict[str, Any]]) -> str:
    rows = [
        "# Engine V0.1 live smoke-test summary",
        "",
        "| Domain | Navigation | Outcome | Usable | Final URL | Redirects | Screenshot | "
        "Duration (s) | Note |",
        "| --- | --- | --- | --- | --- | ---: | --- | ---: | --- |",
    ]
    for result in results:
        row_template = (
            "| {domain} | {navigation} | {outcome} | {usable} | {final_url} | {redirects} | "
            "{screenshot} | {duration:.3f} | {reason} |"
        )
        rows.append(
            row_template.format(
                domain=_table_value(result["input_domain"]),
                navigation=_table_value(result["navigation_status"]),
                outcome=_table_value(result["capture_outcome"]),
                usable="yes" if result["content_usable"] else "no",
                final_url=_table_value(result["final_url"]),
                redirects=result["redirect_count"],
                screenshot=_table_value(result["screenshot_status"]),
                duration=result["duration_seconds"],
                reason=_table_value(result["failure_or_restriction_reason"]),
            )
        )
    return "\n".join(rows) + "\n"


def _table_value(value: object) -> str:
    return str(value or "-").replace("|", "\\|").replace("\n", " ")
