"""In-memory localhost job state for truthful progressive investigation feedback."""

from __future__ import annotations

import copy
import re
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

    def start(
        self,
        runner: JobRunner,
        *,
        target: dict[str, object] | None = None,
    ) -> dict[str, object]:
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
                "target": _bounded_detail(target or {}),
                "started_at": now,
                "updated_at": now,
                "deadline_seconds": self.deadline_seconds,
                "history": [{"stage": "queued", "at": now}],
                "result": None,
                "error": None,
                "visual_state": {
                    "revision": 0,
                    "previews": [],
                    "latest_preview": None,
                    "agent_focus": None,
                },
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

    def preview(self, job_id: str, revision: int | None = None) -> dict[str, object]:
        """Return one internal job-owned preview reference without accepting a path."""

        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise InvestigationJobNotFound(job_id)
            visual = job["visual_state"]
            previews = visual["previews"]
            selected = (
                next(
                    (item for item in previews if item["revision"] == revision),
                    None,
                )
                if revision is not None
                else visual["latest_preview"]
            )
            if selected is None:
                raise InvestigationJobNotFound(f"{job_id}:preview")
            return copy.deepcopy(selected)

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
                job["history"] = job["history"][-48:]
            _apply_visual_update(job, stage=stage, detail=detail, now=now)
            if stage == "page_preview_ready":
                page_title = _short_text(detail.get("page_title"), 256)
                final_url = _short_text(detail.get("url"), 300)
                if page_title is not None:
                    job["target"]["page_title"] = page_title
                if final_url is not None:
                    job["target"]["final_url"] = final_url
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


def _apply_visual_update(
    job: dict[str, Any], *, stage: str, detail: dict[str, object], now: str
) -> None:
    visual = job["visual_state"]
    if stage == "page_preview_ready":
        case_id = _short_text(detail.get("case_id"), 120)
        page_id = _short_text(detail.get("page_id"), 80)
        if case_id is None or page_id is None:
            return
        preview = _append_preview(
            visual,
            {
                "source": "case",
                "case_id": case_id,
                "page_id": page_id,
                "kind": "canonical",
                "verification": "transient",
                "url": _short_text(detail.get("url"), 300),
                "captured_at": _short_text(detail.get("captured_at"), 80) or now,
                "width": _positive_int(detail.get("width")),
                "height": _positive_int(detail.get("height")),
                "sha256": _sha256(detail.get("sha256")),
            },
        )
        visual["agent_focus"] = None
        visual["latest_preview"] = preview
        return
    if stage == "evidence_verified":
        case_id = _short_text(detail.get("case_id"), 120)
        for preview in visual["previews"]:
            if preview.get("source") == "case" and preview.get("case_id") == case_id:
                preview["verification"] = "verified"
        latest = visual.get("latest_preview")
        if isinstance(latest, dict) and latest.get("source") == "case":
            latest["verification"] = "verified"
        return
    if stage not in {
        "agent_focus_ready",
        "interaction_preview_ready",
        "agent_focus_blocked",
    }:
        if stage == "agent_observations_ready" and isinstance(visual.get("agent_focus"), dict):
            visual["agent_focus"].update(
                {
                    "status": "evidence_extracted",
                    "added_observation_count": max(
                        0, _positive_int(detail.get("added_observation_count")) or 0
                    ),
                }
            )
        return

    if stage == "agent_focus_blocked":
        focus = visual.get("agent_focus")
        if isinstance(focus, dict):
            focus.update(
                {
                    "status": "blocked",
                    "reason": _short_text(detail.get("reason"), 200),
                }
            )
        return

    workspace_id = _short_text(detail.get("workspace_id"), 120)
    artifact_name = _short_text(detail.get("artifact_name"), 120)
    if workspace_id is None or artifact_name is None:
        return
    kind = "agent_before" if stage == "agent_focus_ready" else "agent_after"
    preview = _append_preview(
        visual,
        {
            "source": "workspace",
            "workspace_id": workspace_id,
            "artifact_name": artifact_name,
            "page_id": f"interaction-{_positive_int(detail.get('iteration')) or 1:03d}",
            "kind": kind,
            "verification": "persisted",
            "url": _short_text(detail.get("url"), 300),
            "captured_at": now,
            "width": _positive_int(detail.get("viewport_width")),
            "height": _positive_int(detail.get("viewport_height")),
            "sha256": _sha256(detail.get("sha256")),
        },
    )
    focus = visual.get("agent_focus") if isinstance(visual.get("agent_focus"), dict) else {}
    focus.update(
        {
            "status": "selected" if stage == "agent_focus_ready" else "completed",
            "label": _short_text(detail.get("label"), 200),
            "tool_name": _short_text(detail.get("tool_name"), 80),
            "iteration": _positive_int(detail.get("iteration")) or 1,
            "target_bbox": _bounded_box(detail.get("target_bbox")),
            "viewport": {
                "width": _positive_int(detail.get("viewport_width")),
                "height": _positive_int(detail.get("viewport_height")),
            },
        }
    )
    if stage == "agent_focus_ready":
        focus["target_preview_revision"] = preview["revision"]
    else:
        focus["result_preview_revision"] = preview["revision"]
    visual["agent_focus"] = focus
    visual["latest_preview"] = preview


def _append_preview(visual: dict[str, Any], payload: dict[str, object]) -> dict[str, object]:
    visual["revision"] += 1
    preview = {
        "preview_id": f"preview-{visual['revision']:03d}",
        "revision": visual["revision"],
        **payload,
    }
    visual["previews"].append(preview)
    visual["previews"] = visual["previews"][-8:]
    return preview


def _short_text(value: object, limit: int) -> str | None:
    return str(value)[:limit] if isinstance(value, str) and value else None


def _positive_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _sha256(value: object) -> str | None:
    return (
        value.lower()
        if isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{64}", value)
        else None
    )


def _bounded_box(value: object) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    result: dict[str, float] = {}
    for key in ("x", "y", "width", "height"):
        coordinate = value.get(key)
        if not isinstance(coordinate, (int, float)) or isinstance(coordinate, bool):
            return None
        result[key] = max(0.0, min(float(coordinate), 100_000.0))
    return result if result["width"] > 0 and result["height"] > 0 else None


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
        "target": dict(job["target"]),
        "started_at": job["started_at"],
        "updated_at": job["updated_at"],
        "deadline_seconds": job["deadline_seconds"],
        "history": [dict(item) for item in job["history"]],
        "result": job["result"],
        "error": job["error"],
        "visual_state": _public_visual_state(job["visual_state"]),
    }


def _public_visual_state(visual: dict[str, Any]) -> dict[str, object]:
    def public_preview(item: dict[str, object]) -> dict[str, object]:
        return {
            key: copy.deepcopy(value)
            for key, value in item.items()
            if key
            in {
                "preview_id",
                "revision",
                "page_id",
                "kind",
                "verification",
                "url",
                "captured_at",
                "width",
                "height",
            }
        }

    previews = [public_preview(item) for item in visual["previews"]]
    latest = visual.get("latest_preview")
    return {
        "revision": visual["revision"],
        "previews": previews,
        "latest_preview": public_preview(latest) if isinstance(latest, dict) else None,
        "agent_focus": copy.deepcopy(visual.get("agent_focus")),
    }
