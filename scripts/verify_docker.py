"""Build and acceptance-test the local-only Docker deployment."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _run(
    command: list[str],
    *,
    environment: dict[str, str],
    timeout: float = 120,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(  # noqa: S603 - fixed Docker commands
        command,
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout)[-4_000:].strip()
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(command[:5])}\n{detail}"
        )
    return result


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _wait_for_health(port: int, timeout: float = 60) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(  # noqa: S310 - loopback only
                f"http://127.0.0.1:{port}/health", timeout=3
            ) as response:
                if response.status == 200:
                    return json.loads(response.read(100_000))
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
            time.sleep(0.5)
    raise RuntimeError("Container did not become healthy before the acceptance timeout")


def main() -> int:
    project = f"hawkeye-acceptance-{os.getpid()}"
    port = _available_port()
    with tempfile.TemporaryDirectory(prefix="hawkeye-docker-data-") as temporary:
        data_root = Path(temporary).resolve()
        environment = os.environ.copy()
        environment.update(
            {
                "HAWKEYE_PORT": str(port),
                "HAWKEYE_DATA_PATH": str(data_root),
                "HAWKEYE_LLM_BASE_URL": "",
                "HAWKEYE_LLM_API_KEY": "",
                "HAWKEYE_LLM_MODEL": "",
            }
        )
        compose = ["docker", "compose", "--project-name", project]
        results: dict[str, object] = {}
        started = False
        try:
            _run(["docker", "info"], environment=environment, timeout=30)
            _run([*compose, "config", "--quiet"], environment=environment, timeout=30)
            _run(
                [*compose, "up", "--detach", "--build"],
                environment=environment,
                timeout=1_200,
            )
            started = True
            results["health"] = _wait_for_health(port)

            uid = _run(
                [*compose, "exec", "-T", "hawkeye", "id", "-u"],
                environment=environment,
            ).stdout.strip()
            if not uid or uid == "0":
                raise RuntimeError(f"Container must run as non-root, observed uid={uid!r}")
            results["runtime_uid"] = uid

            container_id = _run(
                [*compose, "ps", "-q", "hawkeye"], environment=environment
            ).stdout.strip()
            inspection = json.loads(
                _run(
                    ["docker", "inspect", container_id],
                    environment=environment,
                ).stdout
            )[0]["HostConfig"]
            expected_capabilities = {"SYS_CHROOT"}
            observed_capabilities = {
                capability.removeprefix("CAP_") for capability in (inspection.get("CapAdd") or [])
            }
            if inspection.get("Privileged") is not False:
                raise RuntimeError("Container must not run in privileged mode")
            if inspection.get("ReadonlyRootfs") is not True:
                raise RuntimeError("Container root filesystem must be read-only")
            if set(inspection.get("CapDrop") or []) != {"ALL"}:
                raise RuntimeError("Container must drop all Linux capabilities first")
            if observed_capabilities != expected_capabilities:
                raise RuntimeError(
                    "Container must add back only SYS_CHROOT, observed "
                    f"{sorted(observed_capabilities)!r}"
                )
            security_options = set(inspection.get("SecurityOpt") or [])
            if not any(option.startswith("no-new-privileges") for option in security_options):
                raise RuntimeError("Container must enable no-new-privileges")
            if not any(option.startswith("seccomp=") for option in security_options):
                raise RuntimeError("Container must use the pinned seccomp profile")
            results["container_boundary"] = {
                "privileged": False,
                "read_only_root": True,
                "capabilities": sorted(observed_capabilities),
                "no_new_privileges": True,
                "seccomp": "pinned",
            }

            ocr = _run(
                [*compose, "exec", "-T", "hawkeye", "tesseract", "--version"],
                environment=environment,
            ).stdout.splitlines()[0]
            results["ocr"] = ocr

            browser_code = (
                "from playwright.sync_api import sync_playwright;"
                "from hawkeye.browser import launch_chromium;"
                "p=sync_playwright().start();"
                "b=launch_chromium(p.chromium,headless=True);"
                "page=b.new_page();"
                "page.set_content('<h1>HAWK-EYE container browser</h1>');"
                "assert page.locator('h1').inner_text()=='HAWK-EYE container browser';"
                "b.close();p.stop();print('browser-ok')"
            )
            browser = _run(
                [*compose, "exec", "-T", "hawkeye", "python", "-c", browser_code],
                environment=environment,
                timeout=60,
            ).stdout.strip()
            if browser != "browser-ok":
                raise RuntimeError(f"Unexpected browser smoke output: {browser!r}")
            results["browser"] = browser

            capture_code = "\n".join(
                [
                    "import json, threading",
                    "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer",
                    "from pathlib import Path",
                    "from hawkeye.collector.safety import SafetyPolicy",
                    "from hawkeye.pipeline import investigate",
                    "class FixtureHandler(BaseHTTPRequestHandler):",
                    "    def do_GET(self):",
                    '        body = b"<html><body><main><h1>HAWK-EYE Fixture</h1>" + '
                    'b"<p>Public contact: support@example.test</p></main></body></html>"',
                    "        self.send_response(200)",
                    "        self.send_header('Content-Type', 'text/html; charset=utf-8')",
                    "        self.send_header('Content-Length', str(len(body)))",
                    "        self.end_headers()",
                    "        self.wfile.write(body)",
                    "    def log_message(self, format, *args):",
                    "        return",
                    "class FixtureServer(ThreadingHTTPServer):",
                    "    daemon_threads = True",
                    "server = FixtureServer(('127.0.0.1', 0), FixtureHandler)",
                    "threading.Thread(target=server.serve_forever, daemon=True).start()",
                    "result = investigate(",
                    "    f'http://127.0.0.1:{server.server_port}/',",
                    "    output=Path('/data/acceptance-cases'),",
                    "    case_id='case-container-acceptance',",
                    "    timeout_seconds=15,",
                    "    case_timeout_seconds=30,",
                    "    max_pages=1,",
                    "    max_depth=0,",
                    "    enable_ocr=True,",
                    "    safety_policy=SafetyPolicy(allow_loopback_for_testing=True),",
                    ")",
                    "server.shutdown()",
                    "root = Path(result.case_directory)",
                    "assert result.case.status == 'completed', result.case.error",
                    "assert result.case.page_count == 1",
                    "assert (root / 'screenshots/page-001.png').is_file()",
                    "evidence = json.loads((root / 'evidence.json').read_text(encoding='utf-8'))",
                    "types = {item['type'] for item in evidence}",
                    "assert {'html_page', 'screenshot', 'ocr_metadata'} <= types",
                    "ocr = json.loads((root / 'ocr/page-001.json').read_text(encoding='utf-8'))",
                    "assert ocr['status'] == 'completed', ocr",
                    "print('capture-and-ocr-ok')",
                ]
            )
            capture = _run(
                [*compose, "exec", "-T", "hawkeye", "python", "-c", capture_code],
                environment=environment,
                timeout=90,
            ).stdout.strip()
            if capture != "capture-and-ocr-ok":
                raise RuntimeError(f"Unexpected capture result: {capture!r}")
            results["canonical_capture"] = capture

            timeout_code = "\n".join(
                [
                    "import os, threading, time",
                    "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer",
                    "from pathlib import Path",
                    "from tempfile import TemporaryDirectory",
                    "from hawkeye.collector.safety import SafetyPolicy",
                    "from hawkeye.review_app.live_capture import "
                    "LiveCaptureTimeoutError, run_isolated_live_capture",
                    "class SlowHandler(BaseHTTPRequestHandler):",
                    "    def do_GET(self):",
                    "        time.sleep(60)",
                    "    def log_message(self, format, *args):",
                    "        return",
                    "class TestServer(ThreadingHTTPServer):",
                    "    daemon_threads = True",
                    "server = TestServer(('127.0.0.1', 0), SlowHandler)",
                    "threading.Thread(target=server.serve_forever, daemon=True).start()",
                    "with TemporaryDirectory() as temporary:",
                    "    try:",
                    "        run_isolated_live_capture(",
                    "            f'http://127.0.0.1:{server.server_port}/',",
                    "            output=Path(temporary),",
                    "            case_id='case-container-timeout',",
                    "            safety_policy=SafetyPolicy(allow_loopback_for_testing=True),",
                    "            wall_timeout_seconds=2,",
                    "        )",
                    "    except LiveCaptureTimeoutError:",
                    "        pass",
                    "    else:",
                    "        raise AssertionError('capture did not hit its hard timeout')",
                    "server.shutdown()",
                    "time.sleep(1)",
                    "deadline = time.monotonic() + 8",
                    "survivors = ['not-checked']",
                    "while survivors and time.monotonic() < deadline:",
                    "    survivors = []",
                    "    for candidate in Path('/proc').glob('[0-9]*/cmdline'):",
                    "        if candidate.parent.name == str(os.getpid()):",
                    "            continue",
                    "        try:",
                    "            command = candidate.read_bytes().lower()",
                    "            state = (candidate.parent / 'stat').read_text().split()[2]",
                    "        except (OSError, IndexError):",
                    "            continue",
                    "        active_browser = b'headless_shell' in command",
                    "        active_browser = active_browser or b'/chrome' in command",
                    "        if state != 'Z' and active_browser:",
                    "            survivors.append(str(candidate.parent.name))",
                    "    if survivors:",
                    "        time.sleep(0.25)",
                    "assert not survivors, f'Chromium survivors: {survivors}'",
                    "print('hard-timeout-cleanup-ok')",
                ]
            )
            timeout_cleanup = _run(
                [*compose, "exec", "-T", "hawkeye", "python", "-c", timeout_code],
                environment=environment,
                timeout=30,
            ).stdout.strip()
            if timeout_cleanup != "hard-timeout-cleanup-ok":
                raise RuntimeError(f"Unexpected timeout cleanup result: {timeout_cleanup!r}")
            results["hard_timeout_cleanup"] = timeout_cleanup

            published = _run(
                ["docker", "port", container_id, "8760/tcp"], environment=environment
            ).stdout.strip()
            if not published.startswith("127.0.0.1:"):
                raise RuntimeError(f"Container port is not host-loopback-only: {published!r}")
            results["published_port"] = published

            marker = ".hawkeye-container-acceptance"
            write_marker = (
                "from pathlib import Path;"
                f"Path('/data/{marker}').write_text('persisted',encoding='utf-8')"
            )
            _run(
                [*compose, "exec", "-T", "hawkeye", "python", "-c", write_marker],
                environment=environment,
            )
            _run([*compose, "down"], environment=environment, timeout=120)
            started = False
            _run([*compose, "up", "--detach"], environment=environment, timeout=120)
            started = True
            _wait_for_health(port)
            read_marker = (
                "from pathlib import Path;"
                f"assert Path('/data/{marker}').read_text(encoding='utf-8')=='persisted';"
                "print('persistence-ok')"
            )
            persistence = _run(
                [*compose, "exec", "-T", "hawkeye", "python", "-c", read_marker],
                environment=environment,
            ).stdout.strip()
            if persistence != "persistence-ok":
                raise RuntimeError(f"Unexpected persistence result: {persistence!r}")
            results["restart_persistence"] = persistence
        finally:
            if started:
                _run(
                    [*compose, "down", "--remove-orphans"],
                    environment=environment,
                    timeout=120,
                    check=False,
                )

    print(json.dumps({"status": "ok", **results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
