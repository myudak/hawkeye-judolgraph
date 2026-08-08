"""In-memory localhost job state for truthful progressive investigation feedback."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal

JobStatus = Literal["queued", "running", "completed", "failed"]
JobProgressCallback = Callable[[str, dict[str, object]], None]
JobRunner = Callable[[JobProgressCallback], dict[str, object]]


class InvestigationJobNotFound(KeyError):
    """Raised for an unknown bounded job identifier."""


class InvestigationJobAlreadyRunning(RuntimeError):
    """Raised when the single-machine workspace already has an active capture."""


class InvestigationJobManager:
    """Run one local investigation at a time and expose bounded stage snapshots."""

    def __init__(self, *, deadline_seconds: int = 150) -> None:
        self.deadline_seconds = deadline_seconds
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}

    def start(self, runner: JobRunner) -> dict[str, object]:
        with self._lock:
            active = self._active_unlocked()
            if active is not None:
                raise InvestigationJobAlreadyRunning(
                    f"Investigation {active['job_id']} is still {active['status']}"
                )
            now = datetime.now(UTC).isoformat()
            job_id = f"scan-{uuid.uuid4().hex[:12]}"
            job: dict[str, Any] = {
                "job_id": job_id,
                "status": "queued",
                "stage": "queued",
                "detail": {},
                "started_at": now,
                "updated_at": now,
                "deadline_seconds": self.deadline_seconds,
                "history": [{"stage": "queued", "at": now}],
                "result": None,
                "error": None,
            }
            self._jobs[job_id] = job
        thread = threading.Thread(
            target=self._run,
            args=(job_id, runner),
            name=f"hawkeye-{job_id}",
            daemon=True,
        )
        thread.start()
        return self.status(job_id)

    def status(self, job_id: str) -> dict[str, object]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise InvestigationJobNotFound(job_id)
            return _public_job(job)

    def active(self) -> dict[str, object] | None:
        with self._lock:
            active = self._active_unlocked()
            return _public_job(active) if active is not None else None

    def _active_unlocked(self) -> dict[str, Any] | None:
        return next(
            (
                job
                for job in reversed(list(self._jobs.values()))
                if job["status"] in {"queued", "running"}
            ),
            None,
        )

    def _run(self, job_id: str, runner: JobRunner) -> None:
        self._update(job_id, status="running", stage="validating_seed", detail={})

        def report(stage: str, detail: dict[str, object]) -> None:
            self._update(job_id, status="running", stage=stage, detail=detail)

        try:
            result = runner(report)
        except Exception as error:
            self._update(
                job_id,
                status="failed",
                stage="failed",
                detail={},
                error=str(error)[:500],
            )
            return
        self._update(
            job_id,
            status="completed",
            stage="completed",
            detail={},
            result=result,
        )

    def _update(
        self,
        job_id: str,
        *,
        status: JobStatus,
        stage: str,
        detail: dict[str, object],
        result: dict[str, object] | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            job = self._jobs[job_id]
            now = datetime.now(UTC).isoformat()
            if job["stage"] != stage:
                job["history"].append({"stage": stage, "at": now})
                job["history"] = job["history"][-24:]
            job.update(
                {
                    "status": status,
                    "stage": stage,
                    "detail": _bounded_detail(detail),
                    "updated_at": now,
                    "result": result,
                    "error": error,
                }
            )


def _bounded_detail(detail: dict[str, object]) -> dict[str, object]:
    bounded: dict[str, object] = {}
    for key, value in list(detail.items())[:12]:
        if isinstance(value, str):
            bounded[str(key)[:80]] = value[:300]
        elif isinstance(value, (int, float, bool)) or value is None:
            bounded[str(key)[:80]] = value
    return bounded


def _public_job(job: dict[str, Any]) -> dict[str, object]:
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "stage": job["stage"],
        "detail": dict(job["detail"]),
        "started_at": job["started_at"],
        "updated_at": job["updated_at"],
        "deadline_seconds": job["deadline_seconds"],
        "history": [dict(item) for item in job["history"]],
        "result": job["result"],
        "error": job["error"],
    }
