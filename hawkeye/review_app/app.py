"""FastAPI surface for the local-only, read-only V1 investigator console."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from hawkeye.review_app.loader import (
    CaseIntegrityError,
    CaseLoader,
    CaseNotFoundError,
    case_details,
)

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


def create_app(cases_root: Path | str) -> FastAPI:
    """Create a non-mutating localhost console over one configured local cases root."""

    loader = CaseLoader(cases_root)
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

    @app.get("/health", include_in_schema=False)
    def health() -> dict[str, object]:
        return {"status": "ok", "mode": "local_read_only"}

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
        return case_details(loader.load(case_id))

    @app.get("/api/cases/{case_id}/artifacts/{evidence_id}", include_in_schema=False)
    def get_artifact(case_id: str, evidence_id: str) -> Response:
        artifact = loader.artifact(case_id, evidence_id)
        return Response(
            content=artifact.content,
            media_type=artifact.media_type,
            headers={"Content-Disposition": artifact.disposition},
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
