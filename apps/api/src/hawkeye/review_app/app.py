"""FastAPI surface for the local-only, read-only V1 investigator console."""

from __future__ import annotations

import hashlib
import re
from io import BytesIO
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from PIL import Image
from pydantic import BaseModel, Field, SecretStr
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from hawkeye.collector.safety import SafetyPolicy
from hawkeye.desktop_settings import DesktopSettingsStore
from hawkeye.pipeline import ProgressCallback
from hawkeye.review_app.auth import BasicAuthMiddleware, BasicAuthSettings
from hawkeye.review_app.jobs import (
    InvestigationJobAlreadyRunning,
    InvestigationJobManager,
    InvestigationJobNotFound,
)
from hawkeye.review_app.live_capture import (
    LiveCaptureTimeoutError,
    LiveCaptureWorkerError,
    run_isolated_live_capture,
)
from hawkeye.review_app.loader import (
    CaseIntegrityError,
    CaseLoader,
    CaseNotFoundError,
    case_details,
)
from hawkeye.review_app.public_demo import PublicDemoOrigin
from hawkeye.review_app.workspace import MvpWorkspace
from hawkeye.storage import make_case_id

_STATIC_ROOT = Path(__file__).parent / "static"
_MAX_JOB_PREVIEW_BYTES = 16 * 1024 * 1024
_PUBLIC_STATIC_MEDIA_TYPES = {
    "app-icon-192x192.png": "image/png",
    "app-icon-512x512.png": "image/png",
    "apple-touch-icon.png": "image/png",
    "browserconfig.xml": "application/xml",
    "favicon-16x16.png": "image/png",
    "favicon-32x32.png": "image/png",
    "favicon-48x48.png": "image/png",
    "favicon-96x96.png": "image/png",
    "favicon.ico": "image/x-icon",
    "hawkeye-avatar.png": "image/png",
    "hawkeye-avatar-light.jpg": "image/jpeg",
    "hawkeye-banner.png": "image/png",
    "hawkeye-banner-light.jpg": "image/jpeg",
    "hawkeye-radar-light.jpg": "image/jpeg",
    "maskable-icon-192x192.png": "image/png",
    "maskable-icon-512x512.png": "image/png",
    "mstile-150x150.png": "image/png",
    "og-image-1200x630.png": "image/png",
    "site.webmanifest": "application/manifest+json",
}
_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "base-uri 'none'; "
    "connect-src 'self'; "
    "font-src 'self'; "
    "form-action 'none'; "
    "frame-src 'none'; "
    "img-src 'self' data:; "
    "media-src 'none'; "
    "object-src 'none'; "
    "script-src 'self'; "
    # React and Base UI use bounded inline style attributes for canvas overlays and
    # floating-element geometry. Scripts remain restricted to same-origin files.
    "style-src 'self' 'unsafe-inline'; "
    "worker-src 'none'"
)


class _SecurityHeadersMiddleware:
    """Add a strict, local-only browser policy to every response, including error responses."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"content-security-policy", _CONTENT_SECURITY_POLICY.encode("ascii")),
                        (b"cross-origin-opener-policy", b"same-origin"),
                        (b"cross-origin-resource-policy", b"same-origin"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"cache-control", b"no-store"),
                    ]
                )
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


class _CreateRunRequest(BaseModel):
    scenario_id: str = Field(max_length=100)
    collection_mode: str = Field(default="synthetic_fixture", max_length=30)


class _ReviewRequest(BaseModel):
    assertion_id: str = Field(max_length=100)
    outcome: str = Field(max_length=50)
    reviewer_label: str = Field(max_length=200)
    reason: str = Field(max_length=2000)


class _CollectSeedRequest(BaseModel):
    seed_url: str = Field(min_length=8, max_length=2048)
    investigation_name: str = Field(default="", max_length=120)
    investigation_mode: Literal["guided", "capture_only"] = "guided"


class _DesktopSettingsRequest(BaseModel):
    enabled: bool = True
    base_url: str = Field(default="", max_length=2048)
    model: str = Field(default="", max_length=200)
    api_style: Literal["auto", "responses", "chat_completions"] = "auto"
    timeout_seconds: float = Field(default=15, gt=0, le=60)
    api_key: SecretStr | None = None
    clear_api_key: bool = False


def create_app(
    cases_root: Path | str,
    *,
    comparisons_root: Path | str | None = None,
    workspace_root: Path | str | None = None,
    collection_safety_policy: SafetyPolicy | None = None,
    desktop_settings: DesktopSettingsStore | None = None,
) -> FastAPI:
    """Create the local console; optional MVP writes remain inside one explicit workspace."""

    cases_path = Path(cases_root).expanduser().resolve()
    loader = CaseLoader(cases_path, comparisons_root=comparisons_root)
    active_safety_policy = collection_safety_policy or SafetyPolicy()
    workspace = (
        MvpWorkspace(
            workspace_root,
            cases_root=cases_path,
            safety_policy=active_safety_policy,
        )
        if workspace_root is not None
        else None
    )
    app = FastAPI(
        title="JudolGraph HAWK-EYE Investigator Console",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        debug=False,
    )
    auth_settings = BasicAuthSettings.from_environment()
    public_demo_origin = PublicDemoOrigin.from_environment()
    allowed_hosts = ["127.0.0.1", "localhost"]
    if public_demo_origin is not None:
        allowed_hosts.append(public_demo_origin.hostname)
    if auth_settings is not None:
        app.add_middleware(BasicAuthMiddleware, settings=auth_settings)
    # Middleware insertion is reversed: security headers wrap host validation, which wraps auth.
    # An attacker-controlled Host is therefore rejected before any credential challenge.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    app.add_middleware(_SecurityHeadersMiddleware)

    @app.exception_handler(CaseNotFoundError)
    async def case_not_found(_: Request, __: CaseNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"error": "not_found"})

    @app.exception_handler(CaseIntegrityError)
    async def case_integrity_error(_: Request, __: CaseIntegrityError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"error": "case_integrity_error"})

    @app.exception_handler(ValueError)
    async def bounded_input_error(_: Request, error: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"error": str(error)[:500]})

    @app.exception_handler(LiveCaptureTimeoutError)
    async def live_capture_timeout(_: Request, error: LiveCaptureTimeoutError) -> JSONResponse:
        return JSONResponse(status_code=504, content={"error": str(error)[:500]})

    @app.exception_handler(LiveCaptureWorkerError)
    async def live_capture_worker_error(_: Request, error: LiveCaptureWorkerError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"error": str(error)[:500]})

    @app.exception_handler(InvestigationJobNotFound)
    async def investigation_job_not_found(_: Request, __: InvestigationJobNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"error": "investigation_job_not_found"})

    @app.exception_handler(InvestigationJobAlreadyRunning)
    async def investigation_job_running(
        _: Request, error: InvestigationJobAlreadyRunning
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"error": str(error)[:500]})

    @app.get("/health", include_in_schema=False)
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "mode": "local_bounded_workspace" if workspace else "local_read_only",
        }

    @app.get("/", include_in_schema=False)
    def index() -> Response:
        return _static_response("index.html", "text/html; charset=utf-8")

    @app.get("/assets/styles.css", include_in_schema=False)
    def styles() -> Response:
        return _static_response("styles.css", "text/css; charset=utf-8")

    @app.get("/assets/app.js", include_in_schema=False)
    def script() -> Response:
        return _static_response("app.js", "text/javascript; charset=utf-8")

    @app.get("/assets/chunks/{filename}", include_in_schema=False)
    def script_chunk(filename: str) -> Response:
        if (
            ".." in filename
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}\.js", filename) is None
        ):
            raise HTTPException(status_code=404, detail="Not Found")
        return _static_response(f"chunks/{filename}", "text/javascript; charset=utf-8")

    @app.get("/assets/{filename}", include_in_schema=False)
    def static_asset(filename: str) -> Response:
        media_type = _PUBLIC_STATIC_MEDIA_TYPES.get(filename)
        if media_type is not None:
            return _static_response(filename, media_type)
        if re.fullmatch(r"(?:geist|public-sans)-[A-Za-z0-9_-]{6,100}\.woff2", filename):
            return _static_response(filename, "font/woff2")
        raise HTTPException(status_code=404, detail="Not Found")

    @app.get("/api/cases", include_in_schema=False)
    def list_cases() -> dict[str, object]:
        return {"cases": loader.list_cases()}

    @app.get("/api/cases/{case_id}", include_in_schema=False)
    def get_case(case_id: str) -> dict[str, object]:
        loaded = loader.load(case_id)
        comparisons, comparison_warning = loader.comparisons_for_case(loaded)
        return case_details(
            loaded,
            comparisons=comparisons,
            comparison_integrity_warning=comparison_warning,
        )

    @app.get("/api/cases/{case_id}/artifacts/{evidence_id}", include_in_schema=False)
    def get_artifact(case_id: str, evidence_id: str) -> Response:
        artifact = loader.artifact(case_id, evidence_id)
        return Response(
            content=artifact.content,
            media_type=artifact.media_type,
            headers={"Content-Disposition": artifact.disposition},
        )

    if workspace is not None:
        scan_jobs = InvestigationJobManager(deadline_seconds=150)

        def collect_and_investigate(
            *,
            seed_url: str,
            investigation_name: str,
            guided: bool,
            report: ProgressCallback,
        ) -> dict[str, object]:
            case_id = make_case_id()
            report("validating_seed", {"seed_url": seed_url})
            active_safety_policy.validate_crawl_url(seed_url)
            report("launching_browser", {"case_id": case_id})
            result = run_isolated_live_capture(
                seed_url,
                output=cases_path,
                case_id=case_id,
                safety_policy=active_safety_policy,
                progress_callback=report,
            )
            report("verifying_evidence", {"case_id": result.case.case_id})
            loaded = loader.load(result.case.case_id)
            report("evidence_verified", {"case_id": result.case.case_id})
            report(
                "running_agent",
                {
                    "mode": "guided" if guided else "capture_only",
                    "observation_count": len(result.observations),
                },
            )
            investigation = workspace.create_live_run(
                result,
                known_cases=_known_case_match_context(loader, exclude_case_id=result.case.case_id),
                investigation_name=investigation_name,
                guided=guided,
                progress_callback=report,
            )
            report(
                "classifying_indicators",
                {"observation_count": len(result.observations)},
            )
            details = case_details(loaded, comparisons=[])
            report("building_graph", {"workspace_id": investigation["workspace_id"]})
            return {**details, **investigation}

        @app.post("/api/cases", include_in_schema=False)
        def create_case(payload: _CollectSeedRequest, request: Request) -> dict[str, object]:
            """Collect a bounded same-site case and launch its auditable investigation run."""

            _require_same_origin(request, public_demo_origin=public_demo_origin)
            return collect_and_investigate(
                seed_url=payload.seed_url,
                investigation_name=payload.investigation_name,
                guided=payload.investigation_mode == "guided",
                report=lambda _stage, _detail: None,
            )

        @app.post("/api/investigation-jobs", include_in_schema=False, status_code=202)
        def create_investigation_job(
            payload: _CollectSeedRequest, request: Request
        ) -> dict[str, object]:
            _require_same_origin(request, public_demo_origin=public_demo_origin)
            seed_url = payload.seed_url
            investigation_name = payload.investigation_name
            guided = payload.investigation_mode == "guided"

            def run(report: ProgressCallback) -> dict[str, object]:
                return collect_and_investigate(
                    seed_url=seed_url,
                    investigation_name=investigation_name,
                    guided=guided,
                    report=report,
                )

            return scan_jobs.start(run)

        @app.get("/api/investigation-jobs/active", include_in_schema=False)
        def active_investigation_job() -> dict[str, object]:
            return {"job": scan_jobs.active()}

        @app.get("/api/investigation-jobs/{job_id}", include_in_schema=False)
        def investigation_job_status(job_id: str) -> dict[str, object]:
            return scan_jobs.status(job_id)

        @app.get("/api/investigation-jobs/{job_id}/preview", include_in_schema=False)
        def investigation_job_preview(
            job_id: str,
            revision: int | None = Query(default=None, ge=1, le=10_000),
            thumbnail: bool = Query(default=False),
        ) -> Response:
            preview = scan_jobs.preview(job_id, revision=revision)
            content = _read_job_preview(
                preview,
                loader=loader,
                cases_root=cases_path,
                workspace_root=workspace.root,
            )
            if thumbnail:
                content = _thumbnail_png(content)
            return Response(
                content=content,
                media_type="image/png",
                headers={
                    "Content-Disposition": 'inline; filename="investigation-preview.png"',
                    "X-Hawkeye-Preview-State": str(preview.get("verification", "transient")),
                },
            )

        @app.get("/api/mvp/scenarios", include_in_schema=False)
        def mvp_scenarios() -> dict[str, object]:
            return {"scenarios": workspace.scenarios()}

        @app.get("/api/mvp/capabilities", include_in_schema=False)
        def mvp_capabilities() -> dict[str, object]:
            return workspace.capability_status()

        @app.get("/api/settings", include_in_schema=False)
        def desktop_settings_view() -> dict[str, object]:
            if desktop_settings is None:
                return {
                    "available": False,
                    "enabled": False,
                    "api_key_configured": False,
                    "applies_to": "manual_environment",
                }
            settings = desktop_settings.view()
            settings["capability"] = workspace.capability_status()
            return settings

        @app.put("/api/settings", include_in_schema=False)
        def desktop_settings_update(
            payload: _DesktopSettingsRequest, request: Request
        ) -> dict[str, object]:
            _require_same_origin(request, public_demo_origin=public_demo_origin)
            if desktop_settings is None:
                raise HTTPException(status_code=409, detail="desktop_settings_unavailable")
            if scan_jobs.active() is not None:
                raise HTTPException(status_code=409, detail="settings_locked_during_investigation")
            api_key = payload.api_key.get_secret_value() if payload.api_key is not None else None
            if api_key is not None and len(api_key) > 4096:
                raise HTTPException(status_code=422, detail="API key exceeds 4096 characters")
            try:
                settings = desktop_settings.update(
                    enabled=payload.enabled,
                    base_url=payload.base_url,
                    model=payload.model,
                    api_style=payload.api_style,
                    timeout_seconds=payload.timeout_seconds,
                    api_key=api_key,
                    clear_api_key=payload.clear_api_key,
                )
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
            settings["capability"] = workspace.refresh_model_configuration()
            return settings

        @app.get("/api/mvp/runs", include_in_schema=False)
        def mvp_runs() -> dict[str, object]:
            return {"runs": workspace.list_runs()}

        @app.post("/api/mvp/runs", include_in_schema=False)
        def mvp_create_run(payload: _CreateRunRequest, request: Request) -> dict[str, object]:
            _require_same_origin(request, public_demo_origin=public_demo_origin)
            return workspace.create_run(
                payload.scenario_id, collection_mode=payload.collection_mode
            )

        @app.get("/api/mvp/runs/{workspace_id}", include_in_schema=False)
        def mvp_run_details(workspace_id: str) -> dict[str, object]:
            details = workspace.details(workspace_id)
            source_case_id = details.get("source_case_id")
            if isinstance(source_case_id, str):
                details["source_case"] = case_details(loader.load(source_case_id), comparisons=[])
            candidate_case_id = details.get("candidate_case_id")
            if isinstance(candidate_case_id, str):
                details["candidate_case"] = case_details(
                    loader.load(candidate_case_id), comparisons=[]
                )
            return details

        @app.post("/api/mvp/runs/{workspace_id}/reviews", include_in_schema=False)
        def mvp_review(
            workspace_id: str, payload: _ReviewRequest, request: Request
        ) -> dict[str, object]:
            _require_same_origin(request, public_demo_origin=public_demo_origin)
            return workspace.review(
                workspace_id,
                assertion_id=payload.assertion_id,
                outcome=payload.outcome,
                reviewer_label=payload.reviewer_label,
                reason=payload.reason,
            )

        @app.post("/api/mvp/runs/{workspace_id}/approve", include_in_schema=False)
        def mvp_approve(workspace_id: str, request: Request) -> dict[str, object]:
            _require_same_origin(request, public_demo_origin=public_demo_origin)
            return workspace.approve_recollection(workspace_id)

        @app.get("/api/mvp/runs/{workspace_id}/artifacts/{artifact_name}", include_in_schema=False)
        def mvp_artifact(workspace_id: str, artifact_name: str) -> Response:
            return Response(
                content=workspace.artifact(workspace_id, artifact_name),
                media_type=workspace.artifact_media_type(artifact_name),
                headers={"Content-Disposition": f'attachment; filename="{artifact_name}"'},
            )

        @app.get("/api/mvp/runs/{workspace_id}/export.md", include_in_schema=False)
        def mvp_export_markdown(workspace_id: str) -> Response:
            return Response(
                content=workspace.export_markdown(workspace_id),
                media_type="text/markdown; charset=utf-8",
                headers={"Content-Disposition": 'attachment; filename="summary.md"'},
            )

        @app.get("/api/mvp/runs/{workspace_id}/export.json", include_in_schema=False)
        def mvp_export_json(workspace_id: str) -> Response:
            return Response(
                content=workspace.export_json(workspace_id),
                media_type="application/json",
                headers={"Content-Disposition": 'attachment; filename="case.json"'},
            )

        @app.get("/api/mvp/runs/{workspace_id}/export.zip", include_in_schema=False)
        def mvp_export_archive(workspace_id: str) -> Response:
            return Response(
                content=workspace.export_archive(workspace_id),
                media_type="application/zip",
                headers={"Content-Disposition": 'attachment; filename="hawkeye-case.zip"'},
            )

    return app


def _static_response(filename: str, media_type: str) -> Response:
    """Serve one trusted application asset selected by a fixed or validated local name."""

    path = _STATIC_ROOT / filename
    try:
        content = path.read_bytes()
    except OSError as error:
        raise RuntimeError("Trusted review UI asset is unavailable") from error
    return Response(content=content, media_type=media_type)


def _read_job_preview(
    preview: dict[str, object],
    *,
    loader: CaseLoader,
    cases_root: Path,
    workspace_root: Path,
) -> bytes:
    """Resolve only a server-issued preview reference beneath its configured root."""

    source = preview.get("source")
    if source == "case":
        case_id = preview.get("case_id")
        page_id = preview.get("page_id")
        if not isinstance(case_id, str) or not isinstance(page_id, str):
            raise HTTPException(status_code=404, detail="Preview unavailable")
        if (
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}", case_id) is None
            or re.fullmatch(r"page-[0-9]{3}", page_id) is None
        ):
            raise HTTPException(status_code=404, detail="Preview unavailable")
        root = cases_root.resolve()
        path = (root / case_id / "screenshots" / f"{page_id}.png").resolve()
        if preview.get("verification") == "verified":
            try:
                loaded = loader.load(case_id)
                page = next(item for item in loaded.pages if item.id == page_id)
                if page.screenshot_evidence_id is None:
                    raise StopIteration
                content = loader.artifact(case_id, page.screenshot_evidence_id).content
            except (CaseIntegrityError, CaseNotFoundError, StopIteration) as error:
                raise HTTPException(
                    status_code=409, detail="Preview failed verification"
                ) from error
            return _validate_job_preview(content, preview)
    elif source == "workspace":
        workspace_id = preview.get("workspace_id")
        artifact_name = preview.get("artifact_name")
        if not isinstance(workspace_id, str) or not isinstance(artifact_name, str):
            raise HTTPException(status_code=404, detail="Preview unavailable")
        if (
            re.fullmatch(r"run-[a-z0-9-]{1,80}-[0-9a-f]{8}", workspace_id) is None
            or re.fullmatch(r"interaction-[0-9]{3}(?:-before)?\.png", artifact_name) is None
        ):
            raise HTTPException(status_code=404, detail="Preview unavailable")
        root = workspace_root.resolve()
        path = (root / workspace_id / "artifacts" / artifact_name).resolve()
    else:
        raise HTTPException(status_code=404, detail="Preview unavailable")

    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(status_code=404, detail="Preview unavailable")
    try:
        if path.stat().st_size > _MAX_JOB_PREVIEW_BYTES:
            raise HTTPException(status_code=409, detail="Preview failed validation")
        with path.open("rb") as source_file:
            content = source_file.read(_MAX_JOB_PREVIEW_BYTES + 1)
    except OSError as error:
        raise HTTPException(status_code=404, detail="Preview unavailable") from error
    return _validate_job_preview(content, preview)


def _validate_job_preview(content: bytes, preview: dict[str, object]) -> bytes:
    expected_sha256 = preview.get("sha256")
    expected_width = preview.get("width")
    expected_height = preview.get("height")
    if (
        len(content) > _MAX_JOB_PREVIEW_BYTES
        or len(content) < 24
        or not content.startswith(b"\x89PNG\r\n\x1a\n")
        or content[12:16] != b"IHDR"
        or not isinstance(expected_sha256, str)
        or hashlib.sha256(content).hexdigest() != expected_sha256
    ):
        raise HTTPException(status_code=409, detail="Preview failed validation")
    width = int.from_bytes(content[16:20], "big")
    height = int.from_bytes(content[20:24], "big")
    if (
        not isinstance(expected_width, int)
        or not isinstance(expected_height, int)
        or width != expected_width
        or height != expected_height
        or not 1 <= width <= 10_000
        or not 1 <= height <= 10_000
    ):
        raise HTTPException(status_code=409, detail="Preview dimensions failed validation")
    return content


def _thumbnail_png(content: bytes) -> bytes:
    try:
        with Image.open(BytesIO(content)) as source:
            source.load()
            thumbnail = source.convert("RGB")
            thumbnail.thumbnail((320, 220), Image.Resampling.LANCZOS)
            output = BytesIO()
            thumbnail.save(output, format="PNG", optimize=True)
            return output.getvalue()
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=409, detail="Preview thumbnail failed") from error


def _require_same_origin(
    request: Request, *, public_demo_origin: PublicDemoOrigin | None = None
) -> None:
    """Reject cross-origin mutations and fail closed for an enabled public demo."""

    origins = request.headers.getlist("origin")
    if public_demo_origin is not None:
        if len(origins) != 1:
            raise HTTPException(status_code=403, detail="cross_origin_mutation_blocked")
        origin = origins[0]
        request_hostname = (request.url.hostname or "").casefold()
        if origin == public_demo_origin.origin and request_hostname == public_demo_origin.hostname:
            return
        if request_hostname not in {"127.0.0.1", "localhost"}:
            raise HTTPException(status_code=403, detail="cross_origin_mutation_blocked")
    elif not origins:
        return
    elif len(origins) != 1:
        raise HTTPException(status_code=403, detail="cross_origin_mutation_blocked")
    else:
        origin = origins[0]
    expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
    if origin.rstrip("/") == expected.rstrip("/"):
        return
    raise HTTPException(status_code=403, detail="cross_origin_mutation_blocked")


def _known_case_match_context(
    loader: CaseLoader, *, exclude_case_id: str
) -> list[dict[str, object]]:
    """Build a trusted internal exact-match corpus without exposing it as an API response."""

    context: list[dict[str, object]] = []
    for summary in loader.list_cases():
        case_id = summary.get("case_id")
        if not isinstance(case_id, str) or case_id == exclude_case_id:
            continue
        try:
            loaded = loader.load(case_id)
        except (CaseIntegrityError, CaseNotFoundError):
            continue
        context.append(
            {
                **summary,
                "observations": [
                    {
                        "id": item.id,
                        "observation_type": item.observation_type,
                        "normalized_value": item.normalized_value,
                        "source_artifact_id": item.source_artifact_id,
                        "screenshot_evidence_id": item.screenshot_evidence_id,
                    }
                    for item in loaded.observations
                ],
            }
        )
    return context
