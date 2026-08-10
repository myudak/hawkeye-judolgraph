"""Local-only Uvicorn runner for the V1 investigator console."""

from __future__ import annotations

from pathlib import Path

import uvicorn

from hawkeye.review_app.app import create_app


def run_local_server(
    cases_root: Path | str,
    *,
    port: int = 8760,
    comparisons_root: Path | str | None = None,
    workspace_root: Path | str | None = None,
    host: str = "127.0.0.1",
) -> None:
    """Run a single-process read-only console bound exclusively to 127.0.0.1."""

    if not 1024 <= port <= 65535:
        raise ValueError("port must be between 1024 and 65535")
    if host not in {"127.0.0.1", "0.0.0.0"}:
        raise ValueError("host must be the local CLI or internal container bind address")
    app = create_app(cases_root, comparisons_root=comparisons_root, workspace_root=workspace_root)
    uvicorn.run(
        app,
        host=host,
        port=port,
        access_log=False,
        proxy_headers=False,
        server_header=False,
    )
