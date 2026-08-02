"""One-pass bounded live observation matrix with crawling and interaction disabled."""

from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from hawkeye.pipeline import investigate

LIVE_OBSERVATION_URLS = (
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
    "https://qq101xfw.com",
    "https://qq888bet4cv.com",
)


def run_live_smoke(output: Path | str) -> dict[str, Any]:
    """Run each owner-supplied target once and preserve every outcome without retries."""

    root = Path(output).expanduser().resolve()
    if root.exists():
        raise FileExistsError(f"Refusing to overwrite existing live observation output: {root}")
    root.mkdir(parents=True)
    cases_root = root / "_case-artifacts"
    results: list[dict[str, Any]] = []
    for index, seed_url in enumerate(LIVE_OBSERVATION_URLS, start=1):
        results.append(_run_one(seed_url, root, cases_root, index))

    summary = {
        "schema_version": "1.0",
        "matrix": "GEMASTIK bounded 12-domain qualitative observation matrix",
        "target_count": len(LIVE_OBSERVATION_URLS),
        "interpretation": (
            "Time/session/location-dependent observations only; synthetic fixtures remain "
            "test truth."
        ),
        "limits": {
            "maximum_primary_pages_per_domain": 1,
            "maximum_crawl_depth": 0,
            "maximum_redirects": 5,
            "timeout_seconds_per_attempt": 30,
            "attempts_per_target": 1,
            "fresh_browser_context_per_attempt": True,
            "interaction": False,
            "candidate_recollection": False,
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
    started = time.monotonic()
    case_id = f"observation-{index:02d}-{hostname.replace('.', '-')}"
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
    final_result["attempts"] = 1
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
        "access_outcome": None,
        "capture_adequacy": "failed",
        "extraction_eligible": False,
        "public_status": "collection_failed",
        "limitation_reasons": ["collection did not produce a completed case"],
        "content_usable": False,
        "classification_reasons": ["navigation did not complete"],
        "redirect_count": 0,
        "page_title": None,
        "entity_counts": {},
        "screenshot_status": "unavailable",
        "checkpoint_count": 0,
        "final_visible_text_chars": 0,
        "html_bytes": 0,
        "duration_seconds": duration_seconds,
        "failure_or_restriction_reason": error,
        "case_directory": None,
    }


def _summarize_case(
    seed_url: str, case_directory: str, case: dict[str, Any], duration_seconds: float
) -> dict[str, Any]:
    directory = Path(case_directory)
    entities_path = directory / "entities.json"
    pages_path = directory / "pages.json"
    readiness_path = directory / "capture" / "page-001-readiness.json"
    entities: list[dict[str, Any]] = []
    if entities_path.exists():
        entities = json.loads(entities_path.read_text(encoding="utf-8"))
    pages = json.loads(pages_path.read_text(encoding="utf-8")) if pages_path.exists() else []
    primary = pages[0] if isinstance(pages, list) and pages else {}
    readiness = (
        json.loads(readiness_path.read_text(encoding="utf-8")) if readiness_path.exists() else {}
    )
    checkpoints = readiness.get("checkpoints", []) if isinstance(readiness, dict) else []
    final_checkpoint = checkpoints[-1] if isinstance(checkpoints, list) and checkpoints else {}
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
        "access_outcome": primary.get("access_outcome", case.get("access_outcome")),
        "capture_adequacy": primary.get("capture_adequacy", case.get("capture_adequacy")),
        "extraction_eligible": primary.get("extraction_eligible", case.get("extraction_eligible")),
        "public_status": primary.get("public_status", case.get("public_status")),
        "limitation_reasons": primary.get("limitation_reasons", case.get("limitation_reasons", [])),
        "content_usable": case.get("content_usable") is True,
        "classification_reasons": classification_reasons,
        "redirect_count": len(case.get("redirect_chain", [])),
        "page_title": title,
        "entity_counts": dict(sorted(Counter(entity["type"] for entity in entities).items())),
        "screenshot_status": "captured"
        if (directory / "screenshots" / "page-001.png").exists()
        else "unavailable",
        "checkpoint_count": len(checkpoints),
        "final_visible_text_chars": final_checkpoint.get("visible_text_chars", 0),
        "html_bytes": readiness.get("html_bytes", 0) if isinstance(readiness, dict) else 0,
        "duration_seconds": duration_seconds,
        "failure_or_restriction_reason": error_or_reason,
        "case_directory": case_directory,
    }


def _copy_primary_artifacts(case_directory: Path, target_root: Path) -> dict[str, str | None]:
    sources = {
        "html": case_directory / "pages" / "page-001.html",
        "visible_text": case_directory / "pages" / "page-001-visible.txt",
        "screenshot": case_directory / "screenshots" / "page-001.png",
        "initial_screenshot": case_directory / "screenshots" / "page-001-initial.png",
        "full_page_screenshot": case_directory / "screenshots" / "page-001-full.png",
        "readiness": case_directory / "capture" / "page-001-readiness.json",
        "response_metadata": case_directory / "capture" / "page-001-response.json",
    }
    artifact_paths: dict[str, str | None] = {"case": str(case_directory)}
    for name, source in sources.items():
        suffix = source.suffix or ".bin"
        target = target_root / f"{name.replace('_', '-')}{suffix}"
        if source.exists():
            shutil.copy2(source, target)
        artifact_paths[name] = str(target) if target.exists() else None
    return artifact_paths


def _empty_artifact_paths() -> dict[str, None]:
    return {
        "case": None,
        "html": None,
        "visible_text": None,
        "screenshot": None,
        "initial_screenshot": None,
        "full_page_screenshot": None,
        "readiness": None,
        "response_metadata": None,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        f"{json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)}\n",
        encoding="utf-8",
    )


def _render_summary_markdown(results: list[dict[str, Any]]) -> str:
    rows = [
        "# GEMASTIK bounded live-observation summary",
        "",
        "> Qualitative, time/session/location-dependent observations. Synthetic fixtures remain "
        "test truth.",
        "",
        "| Domain | Public status | Access | Adequacy | Visible chars | HTML bytes | Final URL | "
        "Duration (s) | Limitations / note |",
        "| --- | --- | --- | --- | ---: | ---: | --- | ---: | --- |",
    ]
    for result in results:
        row_template = (
            "| {domain} | {public_status} | {access} | {adequacy} | {visible_chars} | "
            "{html_bytes} | {final_url} | {duration:.3f} | {reason} |"
        )
        rows.append(
            row_template.format(
                domain=_table_value(result["input_domain"]),
                public_status=_table_value(result.get("public_status")),
                access=_table_value(result.get("access_outcome")),
                adequacy=_table_value(result.get("capture_adequacy")),
                visible_chars=result.get("final_visible_text_chars", 0),
                html_bytes=result.get("html_bytes", 0),
                final_url=_table_value(result["final_url"]),
                duration=result["duration_seconds"],
                reason=_table_value(
                    "; ".join(result.get("limitation_reasons", []))
                    or result["failure_or_restriction_reason"]
                ),
            )
        )
    return "\n".join(rows) + "\n"


def _table_value(value: object) -> str:
    return str(value or "-").replace("|", "\\|").replace("\n", " ")
