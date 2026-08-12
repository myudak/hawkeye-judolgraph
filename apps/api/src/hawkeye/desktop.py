"""Windows desktop host for the local HAWK-EYE web application."""

from __future__ import annotations

import argparse
import json
import logging
import multiprocessing
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType
from typing import Any, BinaryIO, Protocol, cast

import uvicorn
from PIL import Image

from hawkeye.desktop_settings import DesktopSettingsStore
from hawkeye.review_app.app import create_app

_APP_NAME = "HAWK-EYE"
_DEFAULT_PORT = 8760
_READY_TIMEOUT_SECONDS = 20.0
_SETTINGS_FILENAME = "settings.env"


class _MsvcrtApi(Protocol):
    LK_NBLCK: int
    LK_UNLCK: int

    def locking(self, file_descriptor: int, mode: int, byte_count: int) -> None: ...


class _SocketApi(Protocol):
    SO_EXCLUSIVEADDRUSE: int


class _WindowsOsApi(Protocol):
    def startfile(self, path: Path) -> None: ...


class _User32Api(Protocol):
    def MessageBoxW(self, owner: int, message: str, title: str, flags: int) -> int: ...


class _WindowsDllApi(Protocol):
    user32: _User32Api


class _CtypesWindowsApi(Protocol):
    windll: _WindowsDllApi


@dataclass(frozen=True)
class DesktopPaths:
    """Stable per-user paths that survive upgrades and uninstall/reinstall cycles."""

    root: Path
    cases: Path
    workspace: Path
    comparisons: Path
    logs: Path
    settings: Path
    runtime: Path
    lock: Path

    @classmethod
    def resolve(cls) -> DesktopPaths:
        configured = os.environ.get("HAWKEYE_DATA_DIR", "").strip()
        if configured:
            root = Path(configured).expanduser().resolve()
        else:
            local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
            base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
            root = (base / _APP_NAME).resolve()
        return cls(
            root=root,
            cases=root / "Data" / "cases",
            workspace=root / "Data" / "workspace",
            comparisons=root / "Data" / "comparisons",
            logs=root / "Logs",
            settings=root / _SETTINGS_FILENAME,
            runtime=root / "runtime.json",
            lock=root / "hawkeye.lock",
        )

    def create(self) -> None:
        for path in (self.cases, self.workspace, self.comparisons, self.logs):
            path.mkdir(parents=True, exist_ok=True)


class _SingleInstance:
    """Hold one non-blocking Windows file lock for the lifetime of the app."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._handle: BinaryIO | None = None

    def acquire(self) -> bool:
        if os.name != "nt":
            return True
        import msvcrt

        msvcrt_api = cast(_MsvcrtApi, msvcrt)

        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = self._path.open("a+b")
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt_api.locking(handle.fileno(), msvcrt_api.LK_NBLCK, 1)
        except OSError:
            handle.close()
            return False
        self._handle = handle
        return True

    def close(self) -> None:
        if self._handle is None:
            return
        if os.name == "nt":
            import msvcrt

            msvcrt_api = cast(_MsvcrtApi, msvcrt)

            self._handle.seek(0)
            try:
                msvcrt_api.locking(self._handle.fileno(), msvcrt_api.LK_UNLCK, 1)
            except OSError:
                pass
        self._handle.close()
        self._handle = None

    def __enter__(self) -> _SingleInstance:
        if not self.acquire():
            raise RuntimeError("another HAWK-EYE instance is already running")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def main(argv: list[str] | None = None) -> int:
    """Start the frozen local service, open the UI, and own its tray lifecycle."""

    args = _parser().parse_args(argv)
    paths = DesktopPaths.resolve()
    paths.create()
    _load_settings(paths.settings)
    logger = _configure_logging(paths.logs / "hawkeye.log")
    _prepare_bundled_tools(logger)
    if args.self_test:
        return _run_frozen_self_test(logger)

    instance = _SingleInstance(paths.lock)
    if not instance.acquire():
        existing_url = _existing_runtime_url(paths.runtime)
        if existing_url is not None:
            webbrowser.open(existing_url, new=2)
            return 0
        _show_error("HAWK-EYE sedang berjalan, tetapi alamat aplikasinya belum siap.")
        return 1

    listener: socket.socket | None = None
    server: uvicorn.Server | None = None
    try:
        listener = _bind_desktop_loopback(args.port)
        actual_port = int(listener.getsockname()[1])
        url = f"http://127.0.0.1:{actual_port}/"
        _write_runtime(paths.runtime, url)

        app = create_app(
            paths.cases,
            comparisons_root=paths.comparisons,
            workspace_root=paths.workspace,
            desktop_settings=DesktopSettingsStore(paths.settings),
        )
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=actual_port,
            access_log=False,
            proxy_headers=False,
            server_header=False,
            log_config=None,
        )
        server = uvicorn.Server(config)
        server_thread = threading.Thread(
            target=server.run,
            kwargs={"sockets": [listener]},
            name="hawkeye-local-server",
            daemon=True,
        )
        server_thread.start()
        if not _wait_until_ready(url, server_thread):
            raise RuntimeError("server lokal tidak siap dalam batas waktu")

        logger.info("HAWK-EYE ready at %s", url)
        if not args.no_browser and os.environ.get("HAWKEYE_NO_BROWSER") != "1":
            webbrowser.open(url, new=2)

        if args.no_tray or os.environ.get("HAWKEYE_NO_TRAY") == "1":
            server_thread.join()
        else:
            _run_tray(url=url, paths=paths, server=server, server_thread=server_thread)
        return 0
    except Exception:
        logger.exception("HAWK-EYE desktop startup failed")
        _show_error(
            f"HAWK-EYE gagal dijalankan. Detail teknis tersimpan di:\n{paths.logs / 'hawkeye.log'}"
        )
        return 1
    finally:
        if server is not None:
            server.should_exit = True
        if listener is not None:
            try:
                listener.close()
            except OSError:
                pass
        paths.runtime.unlink(missing_ok=True)
        instance.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the HAWK-EYE Windows desktop host")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-tray", action="store_true")
    parser.add_argument("--self-test", action="store_true", help=argparse.SUPPRESS)
    return parser


def _requested_port(cli_port: int | None) -> int:
    if cli_port is not None:
        port = cli_port
    else:
        raw = os.environ.get("HAWKEYE_PORT", str(_DEFAULT_PORT)).strip()
        try:
            port = int(raw)
        except ValueError as error:
            raise ValueError("HAWKEYE_PORT must be an integer") from error
    if not 0 <= port <= 65535:
        raise ValueError("desktop port must be between 0 and 65535")
    return port


def _bind_loopback(port: int) -> socket.socket:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if os.name == "nt":
        socket_api = cast(_SocketApi, socket)
        listener.setsockopt(socket.SOL_SOCKET, socket_api.SO_EXCLUSIVEADDRUSE, 1)
    try:
        listener.bind(("127.0.0.1", port))
        listener.listen(128)
    except OSError:
        listener.close()
        raise
    return listener


def _bind_desktop_loopback(cli_port: int | None) -> socket.socket:
    """Use the documented port, but avoid a dead launch when only the default is occupied."""

    port = _requested_port(cli_port)
    try:
        return _bind_loopback(port)
    except OSError:
        if cli_port is not None or "HAWKEYE_PORT" in os.environ or port != _DEFAULT_PORT:
            raise
        return _bind_loopback(0)


def _wait_until_ready(url: str, server_thread: threading.Thread) -> bool:
    deadline = time.monotonic() + _READY_TIMEOUT_SECONDS
    health_url = f"{url.rstrip('/')}/health"
    while time.monotonic() < deadline and server_thread.is_alive():
        if _is_hawkeye_health(health_url):
            return True
        time.sleep(0.1)
    return False


def _is_hawkeye_health(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=0.8) as response:  # noqa: S310
            if response.status != 200:
                return False
            payload = json.loads(response.read(1024))
    except (OSError, ValueError, urllib.error.URLError):
        return False
    return payload.get("status") == "ok" and str(payload.get("mode", "")).startswith("local_")


def _run_tray(
    *,
    url: str,
    paths: DesktopPaths,
    server: uvicorn.Server,
    server_thread: threading.Thread,
) -> None:
    import pystray

    def open_app(_: Any = None, __: Any = None) -> None:
        webbrowser.open(url, new=2)

    def open_data(_: Any = None, __: Any = None) -> None:
        os_api = cast(_WindowsOsApi, os)
        os_api.startfile(paths.root)

    icon = pystray.Icon(
        "hawkeye",
        _load_tray_image(),
        _APP_NAME,
        menu=pystray.Menu(
            pystray.MenuItem("Buka HAWK-EYE", open_app, default=True),
            pystray.MenuItem("Buka folder data", open_data),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Keluar", lambda tray, _: _stop_desktop(tray, server)),
        ),
    )

    def monitor() -> None:
        server_thread.join()
        icon.stop()

    threading.Thread(target=monitor, name="hawkeye-server-monitor", daemon=True).start()
    icon.run()
    server.should_exit = True
    server_thread.join(timeout=10)


def _stop_desktop(icon: Any, server: uvicorn.Server) -> None:
    server.should_exit = True
    icon.stop()


def _load_tray_image() -> Image.Image:
    image_path = _resource_root() / "desktop-assets" / "hawkeye-avatar.png"
    try:
        with Image.open(image_path) as image:
            return image.convert("RGBA").copy()
    except OSError:
        return Image.new("RGBA", (64, 64), "#ec1764")


def _resource_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    return Path(frozen_root) if frozen_root else Path(__file__).resolve().parents[4]


def _prepare_bundled_tools(logger: logging.Logger) -> None:
    if getattr(sys, "frozen", False):
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")
    bundled_tesseract = _resource_root() / "tesseract" / "tesseract.exe"
    if bundled_tesseract.is_file() and not os.environ.get("HAWKEYE_TESSERACT_PATH"):
        os.environ["HAWKEYE_TESSERACT_PATH"] = str(bundled_tesseract)
        logger.info("Using bundled local OCR runtime")


def _run_frozen_self_test(logger: logging.Logger) -> int:
    """Exercise the bundled browser and the spawn path used by live capture workers."""

    from playwright.sync_api import sync_playwright
    from tldextract import TLDExtract

    from hawkeye.browser import launch_chromium

    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue(maxsize=1)
    process = context.Process(target=_desktop_worker_probe, args=(result_queue,))
    process.start()
    process.join(15)
    if process.is_alive():
        process.kill()
        process.join(3)
        logger.error("Frozen multiprocessing self-test timed out")
        return 1
    if process.exitcode != 0 or result_queue.get(timeout=2) != "hawkeye-worker-ok":
        logger.error("Frozen multiprocessing self-test failed")
        return 1

    extracted = TLDExtract(cache_dir=None, suffix_list_urls=())("portal.example.co.id")
    if extracted.top_domain_under_public_suffix != "example.co.id":
        logger.error("Bundled public-suffix snapshot self-test failed")
        return 1

    try:
        with sync_playwright() as playwright:
            browser = launch_chromium(playwright.chromium, headless=True)
            try:
                page = browser.new_page()
                page.set_content("<main data-hawkeye-self-test>HAWK-EYE</main>")
                if page.locator("[data-hawkeye-self-test]").inner_text() != "HAWK-EYE":
                    raise RuntimeError("bundled browser rendered unexpected content")
            finally:
                browser.close()
    except Exception:
        logger.exception("Bundled Chromium self-test failed")
        return 1
    logger.info("Frozen runtime self-test passed")
    return 0


def _desktop_worker_probe(result_queue: Any) -> None:
    result_queue.put("hawkeye-worker-ok")


def _load_settings(path: Path) -> None:
    """Load only HAWKEYE_* settings without replacing process-level configuration."""

    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key.startswith("HAWKEYE_") or not key.replace("_", "").isalnum():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _configure_logging(path: Path) -> logging.Logger:
    logger = logging.getLogger("hawkeye.desktop")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def _write_runtime(path: Path, url: str) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"url": url, "pid": os.getpid()}), encoding="utf-8")
    temporary.replace(path)


def _existing_runtime_url(path: Path) -> str | None:
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            url = str(payload["url"])
        except (OSError, ValueError, KeyError, TypeError):
            time.sleep(0.1)
            continue
        if url.startswith("http://127.0.0.1:") and _is_hawkeye_health(f"{url.rstrip('/')}/health"):
            return url
        time.sleep(0.1)
    return None


def _show_error(message: str) -> None:
    if os.name == "nt":
        import ctypes

        ctypes_api = cast(_CtypesWindowsApi, ctypes)
        ctypes_api.windll.user32.MessageBoxW(0, message, _APP_NAME, 0x10)
    else:
        print(message, file=sys.stderr)
