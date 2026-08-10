"""Internal container entry point; the normal CLI remains loopback-only."""

from __future__ import annotations

import os
from pathlib import Path

from hawkeye.review_app.server import run_local_server


def main() -> None:
    data_root = Path(os.environ.get("HAWKEYE_DATA_DIR", "/data")).expanduser().resolve()
    port = int(os.environ.get("HAWKEYE_PORT", "8760"))
    cases = data_root / "cases"
    workspace = data_root / "workspace"
    comparisons = data_root / "comparisons"
    for directory in (cases, workspace, comparisons):
        directory.mkdir(parents=True, exist_ok=True)
    run_local_server(
        cases,
        workspace_root=workspace,
        comparisons_root=comparisons,
        port=port,
        host="0.0.0.0",  # nosec B104 - Docker publishes this only on host loopback
    )
