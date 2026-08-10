"""Smoke-test the production-like manual server without touching repository data."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _request(url: str) -> tuple[int, bytes]:
    with urllib.request.urlopen(url, timeout=3) as response:  # noqa: S310 - loopback only
        return response.status, response.read(1_000_000)


def _stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
            timeout=10,
        )
    else:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> int:
    static_index = (
        REPOSITORY_ROOT
        / "apps"
        / "api"
        / "src"
        / "hawkeye"
        / "review_app"
        / "static"
        / "index.html"
    )
    if not static_index.is_file():
        raise SystemExit("Production UI is missing; run `pnpm build` first")

    port = _available_port()
    environment = os.environ.copy()
    for name in (
        "HAWKEYE_LLM_BASE_URL",
        "HAWKEYE_LLM_API_KEY",
        "HAWKEYE_LLM_MODEL",
        "CODEX_BASE_URL",
        "CODEX_API_KEY",
        "CODEX_MODEL",
    ):
        environment.pop(name, None)

    creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    with tempfile.TemporaryDirectory(prefix="hawkeye-manual-") as temporary:
        data_root = Path(temporary) / "data"
        log_path = Path(temporary) / "server.log"
        with log_path.open("wb") as log:
            process = subprocess.Popen(  # noqa: S603 - fixed local command
                [
                    sys.executable,
                    "-m",
                    "hawkeye",
                    "app",
                    "--data",
                    str(data_root),
                    "--port",
                    str(port),
                ],
                cwd=REPOSITORY_ROOT,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
                start_new_session=os.name != "nt",
            )
            try:
                deadline = time.monotonic() + 30
                health_body: bytes | None = None
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        break
                    try:
                        status, health_body = _request(f"http://127.0.0.1:{port}/health")
                    except (OSError, urllib.error.URLError):
                        time.sleep(0.2)
                        continue
                    if status == 200:
                        break
                if health_body is None:
                    log.flush()
                    detail = log_path.read_text(encoding="utf-8", errors="replace")[-2_000:]
                    raise RuntimeError(f"Manual server did not become healthy:\n{detail}")
                health = json.loads(health_body)
                if health != {"status": "ok", "mode": "local_bounded_workspace"}:
                    raise RuntimeError(f"Unexpected health response: {health!r}")

                landing_status, landing = _request(f"http://127.0.0.1:{port}/")
                capability_status, capability_body = _request(
                    f"http://127.0.0.1:{port}/api/mvp/capabilities"
                )
                capability = json.loads(capability_body)
                if landing_status != 200 or b"HAWK-EYE" not in landing:
                    raise RuntimeError("Generated landing page was not served by FastAPI")
                if capability_status != 200 or capability.get("state") != "fallback_only":
                    raise RuntimeError(f"Unexpected no-credential capability: {capability!r}")
            finally:
                _stop(process)

    print(
        json.dumps(
            {
                "status": "ok",
                "bind": "127.0.0.1",
                "health": "ok",
                "landing": "served",
                "no_credential_mode": "fallback_only",
                "data_isolation": "temporary_directory",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
