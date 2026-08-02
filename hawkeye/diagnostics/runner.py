"""Fixed-time render diagnostics isolated from the canonical evidence pipeline."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Literal

from PIL import Image
from playwright.sync_api import (
    Download,
    Page,
    Request,
    Route,
    WebSocketRoute,
    sync_playwright,
)
from playwright.sync_api import Error as PlaywrightError

from hawkeye import __version__
from hawkeye.collector.playwright_collector import (
    DEFAULT_MAX_DECLARED_RESPONSE_BYTES,
    DEFAULT_MAX_TOTAL_REQUESTS,
    DEFAULT_VIEWPORT,
    CollectionBudget,
)
from hawkeye.collector.safety import SafetyPolicy, UnsafeUrlError
from hawkeye.diagnostics.models import (
    DiagnosticEvidenceReference,
    RenderCheckpointDelta,
    RenderCheckpointMeasurement,
    RenderDiagnosticsDocument,
)
from hawkeye.review_app.loader import CaseIntegrityError, CaseLoader, LoadedCase

_CHECKPOINT_SCHEDULE_MS = (0, 500, 1_500, 3_000)
_DIAGNOSTICS_DIRECTORY = "diagnostics"
_DIAGNOSTICS_FILENAME = "render-diagnostics.json"
_MAX_ERROR_LENGTH = 500

type _DiagnosticStatus = Literal[
    "stable_across_checkpoints",
    "changed_after_initial_capture",
    "continued_changing_at_budget_end",
    "low_information_across_checkpoints",
    "diagnostic_error",
]


class DiagnosticInputError(ValueError):
    """Raised for an invalid case, page reference, or diagnostic destination."""


class _DiagnosticCollectionError(RuntimeError):
    """Raised when the isolated diagnostic navigation cannot safely continue."""


@dataclass(frozen=True)
class RenderDiagnosticsResult:
    """The generated immutable report and its new in-case diagnostics path."""

    document: RenderDiagnosticsDocument
    path: Path


@dataclass
class _DiagnosticRequestGuard:
    """Request-by-request safety guard matching the public collection boundary."""

    safety: SafetyPolicy
    allowed_navigation_hosts: frozenset[str]
    budget: CollectionBudget
    errors: list[str] = field(default_factory=list)
    fatal_error: str | None = None

    def handle(self, route: Route) -> None:
        request = route.request
        is_navigation = request.is_navigation_request()
        if not self.budget.consume_request():
            self._fatal("Request budget exhausted before diagnostic browser dispatch")
            route.abort()
            return
        try:
            validated = (
                self.safety.validate_crawl_url(request.url, refresh_dns=True)
                if is_navigation
                else self.safety.validate_url(request.url, refresh_dns=True)
            )
        except UnsafeUrlError as error:
            message = f"Unsafe diagnostic request blocked: {error}"
            if is_navigation:
                self._fatal(message)
            else:
                self._record(message)
            route.abort()
            return
        if is_navigation and validated.hostname not in self.allowed_navigation_hosts:
            self._fatal("Diagnostic navigation host is outside the saved case crawl scope")
            route.abort()
            return
        route.continue_()

    def handle_websocket(self, route: WebSocketRoute) -> None:
        self.budget.consume_request()
        self._record("WebSocket blocked during non-interactive render diagnostics")
        route.close()

    def observe_response(self, request: Request, content_length: str | None) -> None:
        try:
            declared_bytes = int(content_length) if content_length is not None else 0
        except ValueError:
            declared_bytes = 0
        if not self.budget.consume_declared_response_bytes(declared_bytes):
            if request.is_navigation_request():
                self._fatal("Declared response-byte budget exhausted during diagnostic navigation")
            else:
                self._record("Declared response-byte budget exhausted during diagnostics")

    def raise_if_fatal(self) -> None:
        if self.fatal_error is not None:
            raise _DiagnosticCollectionError(self.fatal_error)

    def _fatal(self, message: str) -> None:
        self._record(message)
        self.fatal_error = message

    def _record(self, message: str) -> None:
        if len(self.errors) < 20:
            self.errors.append(message[:_MAX_ERROR_LENGTH])


def run_render_diagnostics(
    case_directory: Path | str,
    *,
    page_id: str = "page-001",
    mode: Literal["fixture", "live"],
    timeout_seconds: float = 30.0,
    safety_policy: SafetyPolicy | None = None,
    command: str = "python -m hawkeye diagnose",
) -> RenderDiagnosticsResult:
    """Write one separate fixed-time diagnostic artifact for a verified completed case page."""

    if timeout_seconds <= 0 or timeout_seconds > 30:
        raise DiagnosticInputError(
            "Diagnostic timeout must be greater than zero and at most 30 seconds"
        )
    loaded_case = _load_case(case_directory)
    page = next((item for item in loaded_case.pages if item.id == page_id), None)
    if page is None:
        raise DiagnosticInputError("Requested page ID is absent from the verified completed case")
    source_url = page.final_url or page.normalized_url
    source_evidence_refs = _source_evidence_refs(loaded_case, page_id)
    destination = _diagnostic_destination(loaded_case.directory)
    safety = safety_policy or SafetyPolicy()
    if mode == "fixture" and not safety.allow_loopback_for_testing:
        raise DiagnosticInputError(
            "Fixture diagnostics require the explicit loopback test safety policy"
        )
    if mode == "live" and safety.allow_loopback_for_testing:
        raise DiagnosticInputError(
            "Live diagnostics must not enable the loopback test safety policy"
        )
    start = time.perf_counter()
    errors: list[str] = []
    status: _DiagnosticStatus
    try:
        checkpoints, request_errors = _measure_page(
            source_url,
            safety=safety,
            allowed_navigation_hosts=loaded_case.case.allowed_crawl_hosts,
            timeout_seconds=timeout_seconds,
        )
        errors.extend(request_errors)
        deltas = _deltas(checkpoints)
        status = _diagnostic_status(checkpoints, deltas)
    except _DiagnosticCollectionError as error:
        checkpoints = []
        deltas = []
        errors.append(str(error)[:_MAX_ERROR_LENGTH])
        status = "diagnostic_error"
    document = RenderDiagnosticsDocument(
        generated_at=datetime.now(UTC),
        engine_version=__version__,
        git_commit=_git_commit(),
        command=command,
        collection_mode=mode,
        source_case_id=loaded_case.case.case_id,
        source_case_manifest_sha256=loaded_case.manifest_sha256,
        source_page_id=page_id,
        source_url=source_url,
        source_evidence_refs=source_evidence_refs,
        checkpoint_schedule_ms=list(_CHECKPOINT_SCHEDULE_MS),
        total_diagnostic_time_ms=round((time.perf_counter() - start) * 1000),
        status=status,
        checkpoints=checkpoints,
        deltas=deltas,
        errors=errors,
    )
    path = _write_diagnostics(destination, document)
    return RenderDiagnosticsResult(document=document, path=path)


def _measure_page(
    source_url: str,
    *,
    safety: SafetyPolicy,
    allowed_navigation_hosts: list[str],
    timeout_seconds: float,
) -> tuple[list[RenderCheckpointMeasurement], list[str]]:
    timeout_ms = int(timeout_seconds * 1000)
    allowed_hosts = frozenset(host.rstrip(".").casefold() for host in allowed_navigation_hosts)
    if not allowed_hosts:
        raise _DiagnosticCollectionError("Saved case does not define a bounded allowed crawl host")
    guard = _DiagnosticRequestGuard(
        safety=safety,
        allowed_navigation_hosts=allowed_hosts,
        budget=CollectionBudget(
            max_total_requests=DEFAULT_MAX_TOTAL_REQUESTS,
            max_declared_response_bytes=DEFAULT_MAX_DECLARED_RESPONSE_BYTES,
        ),
    )
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                viewport=DEFAULT_VIEWPORT,
                accept_downloads=False,
                service_workers="block",
            )
            context.route("**/*", guard.handle)
            context.route_web_socket("**/*", guard.handle_websocket)
            page = context.new_page()
            context.on("page", lambda popup: _close_popup(popup, guard))
            page.on("download", lambda download: _cancel_download(download, guard))
            page.on(
                "response",
                lambda response: guard.observe_response(
                    response.request, response.header_value("content-length")
                ),
            )
            page.set_default_timeout(timeout_ms)
            page.set_default_navigation_timeout(timeout_ms)
            page.goto(source_url, wait_until="domcontentloaded", timeout=timeout_ms)
            guard.raise_if_fatal()
            measurements: list[RenderCheckpointMeasurement] = []
            prior_elapsed = 0
            for elapsed in _CHECKPOINT_SCHEDULE_MS:
                if elapsed > prior_elapsed:
                    page.wait_for_timeout(elapsed - prior_elapsed)
                guard.raise_if_fatal()
                measurements.append(_measure_checkpoint(page, elapsed))
                prior_elapsed = elapsed
            context.close()
            browser.close()
    except (PlaywrightError, ValueError) as error:
        raise _DiagnosticCollectionError(f"Diagnostic browser error: {error}") from error
    guard.raise_if_fatal()
    return measurements, guard.errors


def _measure_checkpoint(page: Page, elapsed_ms: int) -> RenderCheckpointMeasurement:
    try:
        metrics = page.evaluate(
            """() => {
                const root = document.documentElement;
                const body = document.body;
                const visibleText = (body?.innerText ?? "").replace(/\\s+/g, " ").trim();
                const height = Math.max(
                    document.body?.scrollHeight ?? 0,
                    document.documentElement?.scrollHeight ?? 0,
                    document.body?.offsetHeight ?? 0,
                    document.documentElement?.offsetHeight ?? 0
                );
                return {
                    document_ready_state: document.readyState,
                    html_bytes: new TextEncoder().encode(root?.outerHTML ?? "").length,
                    visible_text_chars: visibleText.length,
                    element_count: document.querySelectorAll("*").length,
                    anchor_count: document.querySelectorAll("a").length,
                    image_count: document.querySelectorAll("img").length,
                    iframe_count: document.querySelectorAll("iframe").length,
                    canvas_count: document.querySelectorAll("canvas").length,
                    document_height: height
                };
            }"""
        )
        screenshot = page.screenshot(type="png", full_page=False)
    except PlaywrightError as error:
        raise _DiagnosticCollectionError(f"Diagnostic measurement error: {error}") from error
    if not isinstance(metrics, dict):
        raise _DiagnosticCollectionError("Diagnostic page metrics are not a JSON object")
    return RenderCheckpointMeasurement(
        elapsed_ms=elapsed_ms,
        document_ready_state=_metric_string(metrics, "document_ready_state"),
        html_bytes=_metric_int(metrics, "html_bytes"),
        visible_text_chars=_metric_int(metrics, "visible_text_chars"),
        element_count=_metric_int(metrics, "element_count"),
        anchor_count=_metric_int(metrics, "anchor_count"),
        image_count=_metric_int(metrics, "image_count"),
        iframe_count=_metric_int(metrics, "iframe_count"),
        canvas_count=_metric_int(metrics, "canvas_count"),
        document_height=_metric_int(metrics, "document_height"),
        screenshot_sha256=hashlib.sha256(screenshot).hexdigest(),
        screenshot_bytes=len(screenshot),
        screenshot_entropy=_screenshot_entropy(screenshot),
    )


def _deltas(checkpoints: list[RenderCheckpointMeasurement]) -> list[RenderCheckpointDelta]:
    return [
        RenderCheckpointDelta(
            from_elapsed_ms=previous.elapsed_ms,
            to_elapsed_ms=current.elapsed_ms,
            html_bytes_delta=current.html_bytes - previous.html_bytes,
            visible_text_chars_delta=current.visible_text_chars - previous.visible_text_chars,
            element_count_delta=current.element_count - previous.element_count,
            anchor_count_delta=current.anchor_count - previous.anchor_count,
            image_count_delta=current.image_count - previous.image_count,
            iframe_count_delta=current.iframe_count - previous.iframe_count,
            canvas_count_delta=current.canvas_count - previous.canvas_count,
            document_height_delta=current.document_height - previous.document_height,
            screenshot_changed=current.screenshot_sha256 != previous.screenshot_sha256,
            screenshot_entropy_delta=current.screenshot_entropy - previous.screenshot_entropy,
        )
        for previous, current in zip(checkpoints, checkpoints[1:], strict=False)
    ]


def _diagnostic_status(
    checkpoints: list[RenderCheckpointMeasurement], deltas: list[RenderCheckpointDelta]
) -> Literal[
    "stable_across_checkpoints",
    "changed_after_initial_capture",
    "continued_changing_at_budget_end",
    "low_information_across_checkpoints",
]:
    if _low_information(checkpoints):
        return "low_information_across_checkpoints"
    if deltas and _delta_changed(deltas[-1]):
        return "continued_changing_at_budget_end"
    if any(_delta_changed(delta) for delta in deltas):
        return "changed_after_initial_capture"
    return "stable_across_checkpoints"


def _low_information(checkpoints: list[RenderCheckpointMeasurement]) -> bool:
    return bool(checkpoints) and all(
        item.visible_text_chars <= 80
        and item.element_count <= 20
        and item.anchor_count == 0
        and item.image_count == 0
        and item.iframe_count == 0
        and item.canvas_count == 0
        and item.screenshot_entropy <= 0.25
        for item in checkpoints
    )


def _delta_changed(delta: RenderCheckpointDelta) -> bool:
    return any(
        (
            delta.html_bytes_delta,
            delta.visible_text_chars_delta,
            delta.element_count_delta,
            delta.anchor_count_delta,
            delta.image_count_delta,
            delta.iframe_count_delta,
            delta.canvas_count_delta,
            delta.document_height_delta,
            delta.screenshot_changed,
        )
    )


def _load_case(case_directory: Path | str) -> LoadedCase:
    directory = Path(case_directory).expanduser()
    try:
        resolved = directory.resolve(strict=True)
        loader = CaseLoader(resolved.parent)
        return loader.load(resolved.name)
    except (OSError, CaseIntegrityError, KeyError, ValueError) as error:
        raise DiagnosticInputError("Completed case package cannot be integrity-verified") from error


def _source_evidence_refs(
    loaded_case: LoadedCase, page_id: str
) -> list[DiagnosticEvidenceReference]:
    page = next(item for item in loaded_case.pages if item.id == page_id)
    references: list[DiagnosticEvidenceReference] = []
    for evidence_id in (page.html_evidence_id, page.screenshot_evidence_id):
        if evidence_id is None:
            continue
        record = loaded_case.evidence_by_id.get(evidence_id)
        if record is None or record.type not in {"html_page", "screenshot"}:
            raise DiagnosticInputError("Diagnostic page does not have verified canonical evidence")
        references.append(
            DiagnosticEvidenceReference(
                evidence_id=record.id,
                type=record.type,
                sha256=record.sha256,
            )
        )
    if not references:
        raise DiagnosticInputError("Diagnostic page does not have canonical evidence references")
    return references


def _diagnostic_destination(case_root: Path) -> Path:
    diagnostics_directory = case_root / _DIAGNOSTICS_DIRECTORY
    destination = diagnostics_directory / _DIAGNOSTICS_FILENAME
    if _is_reparse_point(diagnostics_directory) or _is_reparse_point(destination):
        raise DiagnosticInputError("Diagnostics directory must not be a symlink or reparse point")
    if destination.exists():
        raise FileExistsError(f"Render diagnostics already exist: {destination}")
    if diagnostics_directory.exists() and not diagnostics_directory.is_dir():
        raise DiagnosticInputError("Diagnostics path is not a directory")
    return destination


def _write_diagnostics(destination: Path, document: RenderDiagnosticsDocument) -> Path:
    diagnostics_directory = destination.parent
    case_root = diagnostics_directory.parent
    try:
        diagnostics_directory.mkdir(exist_ok=True)
        resolved_directory = diagnostics_directory.resolve(strict=True)
    except OSError as error:
        raise DiagnosticInputError("Diagnostics directory cannot be created safely") from error
    if case_root.resolve() not in resolved_directory.parents:
        raise DiagnosticInputError("Diagnostics directory escapes the verified case package")
    serialized = json.dumps(document.model_dump(mode="json"), indent=2, sort_keys=True)
    try:
        with destination.open("x", encoding="utf-8") as output:
            output.write(f"{serialized}\n")
    except OSError as error:
        raise DiagnosticInputError("Render diagnostics cannot be written") from error
    return destination.resolve()


def _metric_int(metrics: dict[str, Any], key: str) -> int:
    value = metrics.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise _DiagnosticCollectionError(f"Diagnostic metric {key} is invalid")
    return value


def _metric_string(metrics: dict[str, Any], key: str) -> str:
    value = metrics.get(key)
    if not isinstance(value, str):
        raise _DiagnosticCollectionError(f"Diagnostic metric {key} is invalid")
    return value[:64]


def _screenshot_entropy(content: bytes) -> float:
    try:
        with Image.open(BytesIO(content)) as image:
            grayscale = image.convert("L")
            pixels = grayscale.width * grayscale.height
            if pixels <= 0:
                raise ValueError("Diagnostic screenshot has no pixels")
            histogram = grayscale.histogram()
    except (OSError, ValueError) as error:
        raise _DiagnosticCollectionError("Diagnostic screenshot cannot be decoded") from error
    return -sum((count / pixels) * math.log2(count / pixels) for count in histogram if count > 0)


def _close_popup(popup: Page, guard: _DiagnosticRequestGuard) -> None:
    guard._record("Popup closed during non-interactive render diagnostics")
    try:
        popup.close(run_before_unload=False)
    except PlaywrightError:
        return


def _cancel_download(download: Download, guard: _DiagnosticRequestGuard) -> None:
    guard._record("Download cancelled during non-interactive render diagnostics")
    try:
        download.cancel()
    except PlaywrightError:
        return


def _is_reparse_point(path: Path) -> bool:
    try:
        stat = path.lstat()
    except FileNotFoundError:
        return False
    attributes = getattr(stat, "st_file_attributes", 0)
    return path.is_symlink() or bool(
        attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _git_commit() -> str | None:
    repository_root = Path(__file__).resolve().parents[2]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            capture_output=True,
            check=False,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    commit = result.stdout.strip()
    return commit if result.returncode == 0 and len(commit) == 40 else None
