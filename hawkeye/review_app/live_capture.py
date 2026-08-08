"""Killable Playwright capture worker for localhost-triggered investigations."""

from __future__ import annotations

import json
import multiprocessing
import os
import queue
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any

from hawkeye.collector.safety import SafetyPolicy
from hawkeye.models import InvestigationResult
from hawkeye.pipeline import ProgressCallback, investigate

LIVE_CAPTURE_WALL_TIMEOUT_SECONDS = 115.0


class LiveCaptureTimeoutError(RuntimeError):
    """Raised when a browser capture exceeds its final wall-clock boundary."""


class LiveCaptureWorkerError(RuntimeError):
    """Raised when an isolated capture worker cannot return a validated result."""


def run_isolated_live_capture(
    seed_url: str,
    *,
    output: Path,
    case_id: str,
    safety_policy: SafetyPolicy,
    wall_timeout_seconds: float = LIVE_CAPTURE_WALL_TIMEOUT_SECONDS,
    progress_callback: ProgressCallback | None = None,
) -> InvestigationResult:
    """Run one public capture in a process that can be stopped with its browser tree."""

    if wall_timeout_seconds <= 0:
        raise ValueError("wall_timeout_seconds must be positive")
    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue(maxsize=64)
    process = context.Process(
        target=_capture_worker,
        args=(result_queue, seed_url, str(output), case_id, safety_policy),
        name=f"hawkeye-capture-{case_id}",
    )
    process.start()
    deadline = monotonic() + wall_timeout_seconds
    result_payload: dict[str, Any] | None = None
    while process.is_alive() and monotonic() < deadline:
        try:
            message = result_queue.get(timeout=0.2)
        except queue.Empty:
            continue
        result_payload = _handle_worker_message(message, progress_callback) or result_payload

    if process.is_alive():
        _terminate_process_tree(process)
        result_queue.close()
        message = f"Capture exceeded the {int(wall_timeout_seconds)} second hard wall-clock budget"
        _mark_timed_out_case(output / case_id, message)
        raise LiveCaptureTimeoutError(message)

    process.join(2)
    wait_deadline = monotonic() + 2
    while result_payload is None and monotonic() < wait_deadline:
        try:
            message = result_queue.get(timeout=0.2)
        except queue.Empty:
            continue
        result_payload = _handle_worker_message(message, progress_callback) or result_payload
    result_queue.close()
    if result_payload is None:
        raise LiveCaptureWorkerError(
            f"Capture worker exited without a result (exit code {process.exitcode})"
        )
    if not result_payload.get("ok"):
        raise LiveCaptureWorkerError(
            str(result_payload.get("error", "Capture worker failed"))[:500]
        )
    return InvestigationResult.model_validate(result_payload["result"])


def _capture_worker(
    result_queue: Any,
    seed_url: str,
    output: str,
    case_id: str,
    safety_policy: SafetyPolicy,
) -> None:
    def report(stage: str, detail: dict[str, object]) -> None:
        result_queue.put({"kind": "progress", "stage": stage, "detail": detail})

    try:
        result = investigate(
            seed_url,
            output=Path(output),
            timeout_seconds=30,
            case_timeout_seconds=100,
            max_pages=3,
            max_depth=1,
            case_id=case_id,
            safety_policy=safety_policy,
            enable_ocr=True,
            progress_callback=report,
        )
    except Exception as error:  # Parent exposes only this bounded failure detail.
        result_queue.put(
            {
                "kind": "result",
                "ok": False,
                "error_type": type(error).__name__,
                "error": str(error)[:500],
            }
        )
        return
    result_queue.put({"kind": "result", "ok": True, "result": result.model_dump(mode="json")})


def _handle_worker_message(
    message: object,
    progress_callback: ProgressCallback | None,
) -> dict[str, Any] | None:
    if not isinstance(message, dict):
        return None
    if message.get("kind") == "progress":
        stage = message.get("stage")
        detail = message.get("detail")
        if isinstance(stage, str) and isinstance(detail, dict) and progress_callback is not None:
            progress_callback(stage, detail)
        return None
    return message if message.get("kind") == "result" else None


def _terminate_process_tree(process: Any) -> None:
    if os.name == "nt" and process.pid is not None:
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
            timeout=10,
        )
    elif process.is_alive():
        process.terminate()
    process.join(5)
    if process.is_alive():
        process.kill()
        process.join(2)


def _mark_timed_out_case(case_directory: Path, message: str) -> None:
    """Change a terminated worker's initial record from running to truthful failed state."""

    case_path = case_directory / "case.json"
    if not case_path.is_file():
        return
    try:
        payload = json.loads(case_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    reasons = list(payload.get("limitation_reasons") or [])
    if "hard_wall_clock_timeout" not in reasons:
        reasons.append("hard_wall_clock_timeout")
    payload.update(
        {
            "status": "failed",
            "completed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "navigation_status": "timed_out",
            "capture_outcome": "timeout",
            "content_usable": False,
            "capture_adequacy": "failed",
            "extraction_eligible": False,
            "extraction_tier": "none",
            "extraction_skip_reason": "hard_wall_clock_timeout",
            "public_status": "timeout",
            "limitation_reasons": reasons,
            "error": message,
        }
    )
    temporary_path = case_path.with_suffix(".json.tmp")
    temporary_path.write_text(
        f"{json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)}\n",
        encoding="utf-8",
    )
    temporary_path.replace(case_path)
    with (case_directory / "run.log").open("a", encoding="utf-8") as output:
        output.write(
            f"{datetime.now(UTC).isoformat()} case_failed reason=hard_wall_clock_timeout\n"
        )
