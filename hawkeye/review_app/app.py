"""FastAPI surface for the local-only, read-only V1 investigator console."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from hawkeye.collector.safety import SafetyPolicy
from hawkeye.pipeline import investigate
from hawkeye.review_app.loader import (
    CaseIntegrityError,
    CaseLoader,
    CaseNotFoundError,
    case_details,
)
from hawkeye.review_app.workspace import MvpWorkspace
from hawkeye.storage import make_case_id

_STATIC_ROOT = Path(__file__).parent / "static"
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
    "style-src 'self'; "
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


def create_app(
    cases_root: Path | str,
    *,
    comparisons_root: Path | str | None = None,
    workspace_root: Path | str | None = None,
    collection_safety_policy: SafetyPolicy | None = None,
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
    # Do not let an attacker-controlled DNS name treat the loopback service as its origin.
    # This runs before routing and ignores Forwarded/X-Forwarded-Host because V1 has no proxy mode.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
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

        @app.post("/api/cases", include_in_schema=False)
        def create_case(payload: _CollectSeedRequest, request: Request) -> dict[str, object]:
            """Collect a bounded same-site case and launch its auditable investigation run."""

            _require_same_origin(request)
            result = investigate(
                payload.seed_url,
                output=cases_path,
                timeout_seconds=30,
                case_timeout_seconds=100,
                max_pages=3,
                max_depth=1,
                case_id=make_case_id(),
                safety_policy=active_safety_policy,
                enable_ocr=True,
            )
            loaded = loader.load(result.case.case_id)
            details = case_details(loaded, comparisons=[])
            investigation = workspace.create_live_run(
                result,
                known_cases=_known_case_match_context(loader, exclude_case_id=result.case.case_id),
                investigation_name=payload.investigation_name,
                guided=payload.investigation_mode == "guided",
            )
            return {**details, **investigation}

        @app.get("/api/mvp/scenarios", include_in_schema=False)
        def mvp_scenarios() -> dict[str, object]:
            return {"scenarios": workspace.scenarios()}

        @app.get("/api/mvp/capabilities", include_in_schema=False)
        def mvp_capabilities() -> dict[str, object]:
            return workspace.capability_status()

        @app.get("/api/mvp/runs", include_in_schema=False)
        def mvp_runs() -> dict[str, object]:
            return {"runs": workspace.list_runs()}

        @app.post("/api/mvp/runs", include_in_schema=False)
        def mvp_create_run(payload: _CreateRunRequest, request: Request) -> dict[str, object]:
            _require_same_origin(request)
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
            _require_same_origin(request)
            return workspace.review(
                workspace_id,
                assertion_id=payload.assertion_id,
                outcome=payload.outcome,
                reviewer_label=payload.reviewer_label,
                reason=payload.reason,
            )

        @app.post("/api/mvp/runs/{workspace_id}/approve", include_in_schema=False)
        def mvp_approve(workspace_id: str, request: Request) -> dict[str, object]:
            _require_same_origin(request)
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
    """Serve one trusted application asset by a fixed name; never expose static path traversal."""

    path = _STATIC_ROOT / filename
    try:
        content = path.read_bytes()
    except OSError as error:
        raise RuntimeError("Trusted review UI asset is unavailable") from error
    return Response(content=content, media_type=media_type)


def _require_same_origin(request: Request) -> None:
    """Reject browser cross-origin mutations even though the server is loopback-only."""

    origin = request.headers.get("origin")
    if origin is None:
        return
    expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
    if origin.rstrip("/") != expected.rstrip("/"):
        from fastapi import HTTPException

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
