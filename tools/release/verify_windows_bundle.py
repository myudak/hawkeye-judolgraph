"""Smoke-test the packaged HAWK-EYE executable and its bundled browser."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def main() -> int:
    args = _parser().parse_args()
    executable = args.executable.resolve()
    if not executable.is_file():
        raise SystemExit(f"Executable not found: {executable}")

    self_test = subprocess.run([executable, "--self-test"], timeout=90, check=False)
    if self_test.returncode != 0:
        raise SystemExit(f"Frozen runtime self-test failed with {self_test.returncode}")

    with tempfile.TemporaryDirectory(prefix="hawkeye-windows-smoke-") as temporary:
        data_root = Path(temporary)
        environment = os.environ.copy()
        environment.update(
            {
                "HAWKEYE_DATA_DIR": str(data_root),
                "HAWKEYE_PORT": "0",
                "HAWKEYE_NO_BROWSER": "1",
                "HAWKEYE_NO_TRAY": "1",
            }
        )
        process = subprocess.Popen(
            [executable, "--no-browser", "--no-tray"],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            url = _wait_for_runtime(data_root / "runtime.json", process, args.timeout)
            health = _read_json(f"{url.rstrip('/')}/health")
            if health.get("status") != "ok" or health.get("mode") != "local_bounded_workspace":
                raise RuntimeError(f"Unexpected health response: {health}")
            landing = _read_bytes(url)
            if b"HAWK-EYE" not in landing or b"<html" not in landing.lower():
                raise RuntimeError("Packaged landing page is incomplete")
        finally:
            _stop_process_tree(process)
    print("Windows bundle smoke test passed")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser


def _wait_for_runtime(path: Path, process: subprocess.Popen[bytes], timeout: float) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"HAWK-EYE exited early with {process.returncode}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            url = str(payload["url"])
        except (OSError, ValueError, KeyError, TypeError):
            time.sleep(0.1)
            continue
        try:
            if _read_json(f"{url.rstrip('/')}/health").get("status") == "ok":
                return url
        except (OSError, ValueError, urllib.error.URLError):
            pass
        time.sleep(0.1)
    raise RuntimeError("Timed out waiting for packaged app health")


def _read_json(url: str) -> dict[str, object]:
    return json.loads(_read_bytes(url))


def _read_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=2) as response:  # noqa: S310
        if response.status != 200:
            raise RuntimeError(f"Unexpected HTTP status {response.status}")
        return response.read(2_000_000)


def _stop_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
            timeout=15,
        )
    else:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
