"""Shared deterministic local HTTP fixture server for browser integration tests."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest


def _html(title: str, body: str) -> bytes:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{title}</title></head><body><p>"
        "This local fixture contains public informational content for deterministic collection "
        "and evidence-graph testing without any interactive activity.</p>"
        f"{body}</body></html>"
    ).encode()


@pytest.fixture
def fixture_server_url() -> Iterator[str]:
    """Serve normal, restriction, and V0.1 crawl fixtures from a loopback-only server."""

    template = (Path(__file__).parent / "fixtures" / "local_landing.html").read_text(
        encoding="utf-8"
    )
    fixture_directory = Path(__file__).parent / "fixtures"
    fixture_pages = {
        "/normal-content.html": "normal_content.html",
        "/unavailable-page.html": "unavailable_page.html",
        "/bot-challenge.html": "bot_challenge.html",
        "/consent-wall.html": "consent_wall.html",
        "/delayed-script-render-shell.html": "delayed_script_render_shell.html",
        "/render-static-complete.html": "render_static_complete.html",
        "/render-shell-500.html": "render_shell_500.html",
        "/render-shell-1500.html": "render_shell_1500.html",
        "/render-continuing.html": "render_continuing.html",
        "/render-sparse-blank.html": "render_sparse_blank.html",
        "/render-canvas-heavy.html": "render_canvas_heavy.html",
        "/render-dom-growth-static.html": "render_dom_growth_static.html",
        "/render-visual-change-static-dom.html": "render_visual_change_static_dom.html",
        "/render-rich-hidden-blank.html": "render-rich-hidden-blank.html",
        "/geo-restriction-wording.html": "geo-restriction-wording.html",
        "/unavailable-by-location.html": "unavailable-by-location.html",
        "/render-long-page.html": "render-long-page.html",
        "/blank-access-challenge.html": "blank-access-challenge.html",
        "/semantic-evidence.html": "semantic-evidence.html",
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            path = urlsplit(self.path).path
            port = self.server.server_port
            status = 200
            headers: dict[str, str] = {}
            content_type = "text/html; charset=utf-8"
            if path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()
                return
            if path == "/canonical-redirect":
                self.send_response(302)
                self.send_header("Location", f"http://localhost:{port}/canonical-final")
                self.end_headers()
                return
            if path == "/redirect-external":
                self.send_response(302)
                self.send_header("Location", "https://outside.example.net/remote")
                self.end_headers()
                return
            if path in fixture_pages:
                body = (fixture_directory / fixture_pages[path]).read_bytes()
            elif path == "/":
                body = template.replace("{{PORT}}", str(port)).encode("utf-8")
            elif path == "/oversized-dom-2mb.html":
                body = _html("Oversized public DOM", "<p>public evidence block</p>" * 90_000)
            elif path == "/oversized-dom-5mb.html":
                body = _html("Oversized public DOM", "<p>public evidence block</p>" * 220_000)
            elif path == "/inside/path":
                body = _html("Internal fixture page", "<p>Internal content.</p>")
            elif path == "/crawl-cycle-root":
                body = _html("Cycle root", '<a href="/crawl-cycle-child">Child</a>')
            elif path == "/crawl-cycle-child":
                body = _html("Cycle child", '<a href="/crawl-cycle-root">Root</a>')
            elif path == "/crawl-variants":
                body = _html(
                    "Variant root",
                    """
                    <a href="/crawl-child/?b=2&a=1&utm_source=fixture#one">First</a>
                    <a href="/crawl-child?a=1&b=2&fbclid=tracking">Second</a>
                    <a href="/crawl-child/?a=1&b=2&gclid=tracking#two">Third</a>
                    """,
                )
            elif path == "/crawl-self-fragment":
                body = _html(
                    "Self fragment root",
                    '<a href="#current">Current page</a><a href="/crawl-child">Child</a>',
                )
            elif path == "/crawl-budget":
                links = "".join(
                    f'<a href="/budget-{number}">Budget {number}</a>' for number in range(1, 8)
                )
                body = _html("Budget root", links)
            elif path.startswith("/budget-"):
                body = _html("Budget child", f"<p>{path}</p>")
            elif path == "/crawl-external-redirect-root":
                body = _html(
                    "External redirect root", '<a href="/redirect-external">External redirect</a>'
                )
            elif path == "/crawl-candidate-root":
                body = _html(
                    "Candidate root",
                    '<a href="https://offers.related.example.net/offer">External candidate</a>',
                )
            elif path == "/crawl-private-resource":
                body = _html(
                    "Private resource root",
                    '<p>Public content.</p><script src="http://private.resource.test/unsafe.js"></script>',
                )
            elif path == "/crawl-request-budget":
                resources = "".join(
                    f'<img src="/request-budget-{number}.png" alt="resource {number}">'
                    for number in range(1, 12)
                )
                body = _html("Request budget root", resources)
            elif path.startswith("/request-budget-") and path.endswith(".png"):
                content_type = "image/png"
                body = b"fixture"
            elif path == "/crawl-response-budget":
                body = _html(
                    "Response budget root",
                    '<script src="/large-response.js"></script><p>Public content.</p>',
                )
            elif path == "/large-response.js":
                content_type = "application/javascript"
                body = b"x" * 5_000
            elif path == "/crawl-popup":
                body = _html(
                    "Popup root",
                    "<p>Public content.</p>"
                    "<script>window.open('/popup-target', '_blank');</script>",
                )
            elif path == "/popup-target":
                body = _html("Popup target", "<p>Should be closed.</p>")
            elif path == "/crawl-download":
                body = _html(
                    "Download root",
                    """
                    <p>Public content.</p>
                    <a id="fixture-download" href="/download.bin" download>Download</a>
                    <script>document.getElementById('fixture-download').click();</script>
                    """,
                )
            elif path == "/download.bin":
                content_type = "application/octet-stream"
                headers["Content-Disposition"] = 'attachment; filename="fixture.bin"'
                body = b"fixture download"
            elif path == "/crawl-non-html-root":
                body = _html("Non HTML root", '<a href="/document.pdf">Document</a>')
            elif path == "/document.pdf":
                content_type = "application/pdf"
                body = b"%PDF-1.4 fixture"
            elif path == "/crawl-timeout-root":
                body = _html(
                    "Timeout root",
                    '<a href="/aaa-slow">Slow child</a><a href="/crawl-child">Normal child</a>',
                )
            elif path == "/aaa-slow":
                time.sleep(1.0)
                body = _html("Slow child", "<p>Slow content.</p>")
            elif path == "/crawl-child":
                body = _html("Crawl child", "<p>Normal child content.</p>")
            elif path == "/crawl-unusable-root":
                body = _html(
                    "Page unavailable",
                    '<h1>Page unavailable</h1><a href="/crawl-child">Fake child</a>',
                )
            elif path == "/canonical-final":
                body = _html(
                    "Canonical final",
                    f'<a href="http://127.0.0.1:{port}/crawl-child">Seed-host child</a>',
                )
            elif path == "/same-content-root":
                body = _html(
                    "Same content root",
                    '<a href="/same-content-a">A</a><a href="/same-content-b">B</a>',
                )
            elif path in {"/same-content-a", "/same-content-b"}:
                body = _html("Same content", "<p>Identical child payload.</p>")
            elif path.endswith(".css"):
                content_type = "text/css"
                body = b"body { background: #fff; }"
            elif path.endswith(".js"):
                content_type = "application/javascript"
                body = b"window.fixtureLoaded = true;"
            elif path.endswith(".png"):
                content_type = "image/png"
                body = b""
            elif path == "/frame.html":
                body = b"<!doctype html><title>Frame</title>"
            else:
                status = 404
                content_type = "text/plain; charset=utf-8"
                body = b"not found"
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionAbortedError):
                return

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
