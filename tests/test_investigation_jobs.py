"""Bounded progressive job state and isolated-browser failure tests."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from hawkeye.collector.safety import SafetyPolicy
from hawkeye.review_app.jobs import (
    InvestigationJobAlreadyRunning,
    InvestigationJobManager,
)
from hawkeye.review_app.live_capture import (
    LiveCaptureTimeoutError,
    run_isolated_live_capture,
)
from hawkeye.storage import make_case_id


def _wait_for_job(manager: InvestigationJobManager, job_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        status = manager.status(job_id)
        if status["status"] in {"completed", "failed"}:
            return status
        time.sleep(0.01)
    raise AssertionError("Investigation job did not finish within the test deadline")


def test_job_records_truthful_stage_history_and_result() -> None:
    manager = InvestigationJobManager(deadline_seconds=12)

    def run(report):  # type: ignore[no-untyped-def]
        report("capturing_page", {"page_id": "page-001", "ignored": ["not public"]})
        report("preserving_artifacts", {"page_id": "page-001"})
        return {"workspace_id": "run-test"}

    created = manager.start(run)
    completed = _wait_for_job(manager, str(created["job_id"]))

    assert completed["status"] == "completed"
    assert completed["result"] == {"workspace_id": "run-test"}
    assert [item["stage"] for item in completed["history"]] == [
        "queued",
        "validating_seed",
        "capturing_page",
        "preserving_artifacts",
        "completed",
    ]


def test_job_manager_allows_only_one_active_local_capture() -> None:
    manager = InvestigationJobManager()
    release = threading.Event()

    def run(_report):  # type: ignore[no-untyped-def]
        release.wait(1)
        return {"workspace_id": "run-one"}

    first = manager.start(run)
    with pytest.raises(InvestigationJobAlreadyRunning):
        manager.start(run)
    release.set()
    assert _wait_for_job(manager, str(first["job_id"]))["status"] == "completed"


def test_isolated_browser_has_a_hard_wall_clock_stop(tmp_path: Path) -> None:
    started = time.monotonic()
    with pytest.raises(LiveCaptureTimeoutError):
        run_isolated_live_capture(
            "http://127.0.0.1:9/never-reached",
            output=tmp_path,
            case_id=make_case_id(),
            safety_policy=SafetyPolicy(allow_loopback_for_testing=True),
            wall_timeout_seconds=0.05,
        )
    assert time.monotonic() - started < 12
