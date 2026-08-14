"""One-page Playwright collection with request-by-request safety revalidation."""

from __future__ import annotations

import base64
import binascii
import hashlib
import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from io import BytesIO
from urllib.parse import urljoin

from PIL import Image
from playwright.sync_api import (
    CDPSession,
    Download,
    Page,
    Request,
    Response,
    Route,
    ViewportSize,
    WebSocketRoute,
    sync_playwright,
)
from playwright.sync_api import (
    Error as PlaywrightError,
)

from hawkeye.browser import launch_chromium
from hawkeye.models import (
    BlockedRequestRecord,
    CaptureAdequacy,
    CaptureCheckpoint,
    CaptureCheckpointDelta,
    CaptureReadiness,
    CollectedPage,
    RedirectRecord,
    SemanticElementSnapshot,
)

from .safety import SafetyPolicy, UnsafeUrlError

VIEWPORT_WIDTH = 1440
VIEWPORT_HEIGHT = 1024
DEFAULT_VIEWPORT: ViewportSize = {"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}
DEFAULT_USER_AGENT = "JudolGraph-HAWKEYE/0.2 (+public-evidence-collection)"
ALLOWED_HTML_CONTENT_TYPES = frozenset({"text/html", "application/xhtml+xml"})
MAX_BLOCKED_REQUEST_RECORDS = 100
DEFAULT_MAX_TOTAL_REQUESTS = 200
DEFAULT_MAX_DECLARED_RESPONSE_BYTES = 10_000_000
CAPTURE_CHECKPOINT_SCHEDULE_MS = (0, 500, 1500, 3000)
CAPTURE_SETTLE_EXTENSION_MS = (5000, 8000)
PERSISTED_HTML_LIMIT_BYTES = 5_000_000
DIRECT_EXTRACTOR_LIMIT_BYTES = 2_000_000
MAX_FULL_PAGE_HEIGHT = 12_000
COLLECTOR_VERSION = "g10-bounded-settle-scroll-2"
CAPTURE_POLICY_VERSION = "public-read-only-v3"


@dataclass
class CollectionBudget:
    """Mutable, case-shared hard limits for browser traffic observed by collectors."""

    max_total_requests: int = DEFAULT_MAX_TOTAL_REQUESTS
    max_declared_response_bytes: int = DEFAULT_MAX_DECLARED_RESPONSE_BYTES
    request_count: int = 0
    declared_response_bytes: int = 0
    exhausted_reason: str | None = None

    def consume_request(self) -> bool:
        self.request_count += 1
        if self.request_count > self.max_total_requests:
            self.exhausted_reason = "request_budget"
            return False
        return True

    def consume_declared_response_bytes(self, declared_bytes: int) -> bool:
        self.declared_response_bytes += max(declared_bytes, 0)
        if self.declared_response_bytes > self.max_declared_response_bytes:
            self.exhausted_reason = "response_budget"
            return False
        return True


class CollectionError(RuntimeError):
    """Raised when a browser collection cannot produce a safe rendered HTML page."""

    def __init__(
        self,
        message: str,
        *,
        reason_code: str = "navigation_error",
        blocked_requests: Iterable[BlockedRequestRecord] = (),
        redirects: Iterable[RedirectRecord] = (),
        blocked_popup_count: int = 0,
        blocked_download_count: int = 0,
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.blocked_requests = list(blocked_requests)
        self.redirects = list(redirects)
        self.blocked_popup_count = blocked_popup_count
        self.blocked_download_count = blocked_download_count


@dataclass
class _RequestGuard:
    """Blocks unsafe browser traffic before dispatch and limits navigation redirects."""

    safety: SafetyPolicy
    max_redirects: int
    budget: CollectionBudget
    allowed_navigation_hosts: frozenset[str] | None = None
    navigation_urls: list[str] = field(default_factory=list)
    redirect_count: int = 0
    redirects: list[RedirectRecord] = field(default_factory=list)
    navigation_failure: CollectionError | None = None
    blocked_requests: list[BlockedRequestRecord] = field(default_factory=list)
    stop_page: Callable[[], None] | None = None

    def handle(self, route: Route) -> None:
        request = route.request
        # Playwright also calls ``is_navigation_request`` true for iframe documents.  Only the
        # main frame changes the page being collected; treating a public third-party iframe as a
        # crawl navigation can incorrectly fail an otherwise valid capture.
        is_navigation = request.is_navigation_request() and request.frame.parent_frame is None
        if not self.budget.consume_request():
            self._blocked(
                request,
                reason="request_budget: maximum browser request count exceeded",
                is_navigation=is_navigation,
            )
            self.navigation_failure = self._failure(
                "Request budget exceeded before browser dispatch", reason_code="request_budget"
            )
            route.abort()
            if self.stop_page is not None:
                self.stop_page()
            return
        try:
            validated = (
                self.safety.validate_crawl_url(request.url, refresh_dns=True)
                if is_navigation
                # The first request to each subresource authority resolves and validates every
                # address.  Later requests reuse that case-local result, matching Chromium's own
                # bounded browser-context DNS cache without serializing hundreds of identical DNS
                # lookups on resource-heavy pages.  Every main-frame navigation is still
                # re-resolved immediately before dispatch.
                else self.safety.validate_url(request.url)
            )
        except UnsafeUrlError as error:
            self._blocked(
                request,
                reason=f"unsafe_destination: {error}",
                is_navigation=is_navigation,
            )
            if is_navigation:
                self.navigation_failure = self._failure(
                    f"Unsafe navigation target blocked: {error}", reason_code="unsafe_destination"
                )
            route.abort()
            return

        if is_navigation:
            if (
                self.allowed_navigation_hosts is not None
                and validated.hostname not in self.allowed_navigation_hosts
            ):
                self._blocked(
                    request,
                    reason=(
                        "external_host: navigation host is outside the bounded crawl scope "
                        f"({validated.hostname})"
                    ),
                    is_navigation=True,
                )
                self.navigation_failure = self._failure(
                    f"Navigation target outside allowed crawl hosts: {validated.hostname}",
                    reason_code="external_host",
                )
                route.abort()
                return
            if len(self.navigation_urls) >= self.max_redirects + 1:
                self._blocked(
                    request,
                    reason="redirect_limit: maximum redirect count exceeded",
                    is_navigation=True,
                )
                self.navigation_failure = self._failure(
                    f"Redirect limit exceeded: maximum {self.max_redirects} redirects allowed",
                    reason_code="redirect_limit",
                )
                route.abort()
                return
            self.navigation_urls.append(validated.normalized_url)
        route.continue_()

    def handle_websocket(self, route: WebSocketRoute) -> None:
        """Do not permit persistent sockets in the no-interaction collection context."""

        self.budget.consume_request()
        self._record_blocked(
            url=route.url,
            resource_type="websocket",
            reason="websocket_disabled: persistent browser sockets are outside collection scope",
            is_navigation=False,
        )
        route.close()

    def reject_navigation_url(self, url: str, *, reason: str, reason_code: str) -> None:
        """Record a navigation discovered in response headers and fail the collection."""

        self._record_blocked(
            url=url,
            resource_type="document",
            reason=reason,
            is_navigation=True,
        )
        self.navigation_failure = self._failure(reason, reason_code=reason_code)

    def observe_redirect(self, record: RedirectRecord) -> None:
        """Keep response-header redirect facts even when policy stops navigation."""

        self.redirects.append(record)

    def consume_declared_response_bytes(self, response: Response) -> bool:
        """Charge each response's declared body size to the shared case budget."""

        raw_length = response.header_value("content-length")
        try:
            declared_bytes = int(raw_length) if raw_length is not None else 0
        except ValueError:
            declared_bytes = 0
        return self.budget.consume_declared_response_bytes(declared_bytes)

    def fail_for_response_budget(self, response: Response) -> None:
        self._record_blocked(
            url=response.url,
            resource_type=response.request.resource_type,
            reason="response_budget: declared response-byte budget exceeded",
            is_navigation=response.request.is_navigation_request(),
        )
        self.navigation_failure = self._failure(
            "Declared response-byte budget exceeded", reason_code="response_budget"
        )

    def _blocked(
        self, request: Request, *, reason: str, is_navigation: bool
    ) -> BlockedRequestRecord:
        return self._record_blocked(
            url=request.url,
            resource_type=request.resource_type,
            reason=reason,
            is_navigation=is_navigation,
        )

    def _record_blocked(
        self, *, url: str, resource_type: str, reason: str, is_navigation: bool
    ) -> BlockedRequestRecord:
        record = BlockedRequestRecord(
            url=url,
            resource_type=resource_type,
            reason=reason,
            is_navigation=is_navigation,
        )
        if len(self.blocked_requests) < MAX_BLOCKED_REQUEST_RECORDS:
            self.blocked_requests.append(record)
        return record

    def _failure(self, message: str, *, reason_code: str) -> CollectionError:
        return CollectionError(
            message,
            reason_code=reason_code,
            blocked_requests=self.blocked_requests,
            redirects=self.redirects,
        )


class BrowserCollector:
    """Collect exactly one rendered public HTML page without user interactions."""

    def __init__(
        self,
        *,
        safety: SafetyPolicy,
        timeout_seconds: float = 30.0,
        max_redirects: int = 5,
        max_html_bytes: int = PERSISTED_HTML_LIMIT_BYTES,
        budget: CollectionBudget | None = None,
        allowed_navigation_hosts: Iterable[str] | None = None,
        headed: bool = False,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        if timeout_seconds <= 0 or timeout_seconds > 30:
            raise ValueError("timeout_seconds must be greater than zero and at most 30")
        if max_redirects < 0 or max_redirects > 5:
            raise ValueError("max_redirects must be between zero and five")
        if max_html_bytes <= 0:
            raise ValueError("max_html_bytes must be positive")
        self.safety = safety
        self.timeout_seconds = timeout_seconds
        self.max_redirects = max_redirects
        self.max_html_bytes = max_html_bytes
        self.budget = budget or CollectionBudget()
        self.allowed_navigation_hosts = (
            frozenset(host.rstrip(".").casefold() for host in allowed_navigation_hosts)
            if allowed_navigation_hosts is not None
            else None
        )
        self.headed = headed
        self.user_agent = user_agent

    def collect(self, seed_url: str) -> CollectedPage:
        """Navigate once and preserve a fixed-time, non-interactive canonical browser state."""

        validated_seed = self.safety.validate_crawl_url(seed_url, refresh_dns=True)
        if (
            self.allowed_navigation_hosts is not None
            and validated_seed.hostname not in self.allowed_navigation_hosts
        ):
            raise CollectionError(
                f"Navigation target outside allowed crawl hosts: {validated_seed.hostname}",
                reason_code="external_host",
            )
        timeout_ms = int(self.timeout_seconds * 1000)
        guard = _RequestGuard(
            safety=self.safety,
            max_redirects=self.max_redirects,
            budget=self.budget,
            allowed_navigation_hosts=self.allowed_navigation_hosts,
        )
        blocked_popup_count = 0
        blocked_download_count = 0

        with sync_playwright() as playwright:
            browser = launch_chromium(playwright.chromium, headless=not self.headed)
            browser_version = browser.version
            context = browser.new_context(
                user_agent=self.user_agent,
                viewport=DEFAULT_VIEWPORT,
                accept_downloads=False,
                service_workers="block",
            )
            context.route("**/*", guard.handle)
            context.route_web_socket("**/*", guard.handle_websocket)
            page = context.new_page()
            cdp_session = context.new_cdp_session(page)
            cdp_session.send("Network.enable")
            last_document_content_type: str | None = None

            def record_document_response(payload: dict[str, object]) -> None:
                """Retain the MIME type even when Chromium turns a document into a download.

                Playwright does not consistently emit its high-level ``response`` event for a
                top-level PDF/download before ``goto`` returns ``ERR_ABORTED``. Chromium's network
                event is still emitted and lets the collector preserve the precise reason without
                guessing from a URL suffix.
                """

                nonlocal last_document_content_type
                if payload.get("type") != "Document":
                    return
                response = payload.get("response")
                if not isinstance(response, dict):
                    return
                mime_type = response.get("mimeType")
                if isinstance(mime_type, str) and mime_type:
                    last_document_content_type = mime_type.split(";", maxsplit=1)[0].casefold()

            cdp_session.on("Network.responseReceived", record_document_response)
            guard.stop_page = lambda: _stop_page(page)
            page.set_default_timeout(timeout_ms)
            page.set_default_navigation_timeout(timeout_ms)

            def close_popup(popup: Page) -> None:
                nonlocal blocked_popup_count
                if popup is page:
                    return
                blocked_popup_count += 1
                try:
                    popup.close(run_before_unload=False)
                except PlaywrightError:
                    return

            def cancel_download(download: Download) -> None:
                nonlocal blocked_download_count
                blocked_download_count += 1
                try:
                    download.cancel()
                except PlaywrightError:
                    return

            context.on("page", close_popup)
            page.on("download", cancel_download)

            def inspect_navigation_response(response: Response) -> None:
                """Stop a redirect or non-HTML document before it becomes a crawl result.

                Playwright's route hook handles the first request in a redirect chain, but browser
                engines may advance subsequent redirect targets without invoking that hook. The
                response listener validates the Location header before allowing the page to keep
                navigating, then closes this ephemeral page on a policy violation.
                """

                request = response.request
                if guard.navigation_failure is not None:
                    return
                if not guard.consume_declared_response_bytes(response):
                    guard.fail_for_response_budget(response)
                    _stop_page(page)
                    return
                if not request.is_navigation_request():
                    return
                if 300 <= response.status < 400:
                    location = response.header_value("location")
                    if not location:
                        return
                    target_url = urljoin(response.url, location)
                    guard.observe_redirect(
                        RedirectRecord(
                            source_url=response.url,
                            destination_url=target_url,
                            status_code=response.status,
                            raw_location=location,
                            resource_type=request.resource_type,
                            is_top_level_navigation=request.frame == page.main_frame,
                        )
                    )
                    guard.redirect_count += 1
                    if guard.redirect_count > self.max_redirects:
                        guard.reject_navigation_url(
                            target_url,
                            reason=(
                                "Redirect limit exceeded: "
                                f"maximum {self.max_redirects} redirects allowed"
                            ),
                            reason_code="redirect_limit",
                        )
                        _stop_page(page)
                        return
                    try:
                        target = self.safety.validate_crawl_url(target_url, refresh_dns=True)
                    except UnsafeUrlError as error:
                        guard.reject_navigation_url(
                            target_url,
                            reason=f"Unsafe redirect target blocked: {error}",
                            reason_code="unsafe_destination",
                        )
                        _stop_page(page)
                        return
                    if (
                        self.allowed_navigation_hosts is not None
                        and target.hostname not in self.allowed_navigation_hosts
                    ):
                        guard.reject_navigation_url(
                            target_url,
                            reason=(
                                f"Navigation target outside allowed crawl hosts: {target.hostname}"
                            ),
                            reason_code="external_host",
                        )
                        _stop_page(page)
                    return
                content_type = (
                    (response.header_value("content-type") or "")
                    .split(";", maxsplit=1)[0]
                    .casefold()
                )
                if content_type not in ALLOWED_HTML_CONTENT_TYPES:
                    guard.reject_navigation_url(
                        response.url,
                        reason=(
                            f"Unsupported content type for collection: {content_type or 'missing'}"
                        ),
                        reason_code="unsupported_content_type",
                    )
                    # Keep the page alive until ``goto`` observes the recorded failure. Closing it
                    # inside the asynchronous response callback can win the race and replace the
                    # precise content-type reason with a generic "Target closed" navigation error.

            page.on("response", inspect_navigation_response)
            try:
                response = page.goto(
                    validated_seed.normalized_url,
                    wait_until="domcontentloaded",
                    timeout=timeout_ms,
                )
                if guard.navigation_failure is not None:
                    raise self._with_browser_counts(
                        guard.navigation_failure, blocked_popup_count, blocked_download_count
                    )
                if response is None:
                    raise self._error(
                        "Navigation returned no response",
                        guard,
                        blocked_popup_count,
                        blocked_download_count,
                    )

                content_type = self._require_html_response(
                    response, guard, blocked_popup_count, blocked_download_count
                )
                final = self.safety.validate_crawl_url(page.url, refresh_dns=True)
                if (
                    self.allowed_navigation_hosts is not None
                    and final.hostname not in self.allowed_navigation_hosts
                ):
                    raise self._error(
                        f"Navigation target outside allowed crawl hosts: {final.hostname}",
                        guard,
                        blocked_popup_count,
                        blocked_download_count,
                        reason_code="external_host",
                    )
                redirects = _redirect_records(response.request, page)
                redirect_chain = [entry.source_url for entry in redirects]
                if len(redirect_chain) > self.max_redirects:
                    raise self._error(
                        f"Redirect limit exceeded: observed {len(redirect_chain)} redirects, "
                        f"maximum is {self.max_redirects}",
                        guard,
                        blocked_popup_count,
                        blocked_download_count,
                        reason_code="redirect_limit",
                    )
                checkpoints: list[CaptureCheckpoint] = []
                checkpoint_screenshots: list[bytes] = []
                visible_text = ""
                html = ""
                prior_elapsed = 0
                for elapsed_ms in CAPTURE_CHECKPOINT_SCHEDULE_MS:
                    if elapsed_ms > prior_elapsed:
                        page.wait_for_timeout(elapsed_ms - prior_elapsed)
                    if guard.navigation_failure is not None:
                        raise self._with_browser_counts(
                            guard.navigation_failure,
                            blocked_popup_count,
                            blocked_download_count,
                        )
                    checkpoint, checkpoint_screenshot, visible_text, html = _capture_checkpoint(
                        page,
                        cdp_session=cdp_session,
                        elapsed_ms=elapsed_ms,
                    )
                    checkpoints.append(checkpoint)
                    checkpoint_screenshots.append(checkpoint_screenshot)
                    prior_elapsed = elapsed_ms
                # Modern client-rendered pages often become information-rich exactly at the old
                # three-second boundary.  A fixed, bounded settle extension lets the collector
                # distinguish late rendering from a page that genuinely never stabilizes.  The
                # extension is used only when the canonical state is already public, visible, and
                # still changing; it never clicks, scrolls, dismisses, or waits on network-idle.
                base_deltas = _checkpoint_deltas(checkpoints)
                if (
                    base_deltas
                    and base_deltas[-1].material_change
                    and not _low_information(checkpoints[-1])
                    and not _visual_dom_mismatch(checkpoints[-1])
                ):
                    for elapsed_ms in CAPTURE_SETTLE_EXTENSION_MS:
                        page.wait_for_timeout(elapsed_ms - prior_elapsed)
                        if guard.navigation_failure is not None:
                            raise self._with_browser_counts(
                                guard.navigation_failure,
                                blocked_popup_count,
                                blocked_download_count,
                            )
                        checkpoint, checkpoint_screenshot, visible_text, html = _capture_checkpoint(
                            page,
                            cdp_session=cdp_session,
                            elapsed_ms=elapsed_ms,
                        )
                        checkpoints.append(checkpoint)
                        checkpoint_screenshots.append(checkpoint_screenshot)
                        prior_elapsed = elapsed_ms
                        extended_deltas = _checkpoint_deltas(checkpoints)
                        if extended_deltas and not extended_deltas[-1].material_change:
                            break
                if _bounded_scroll_discovery(page):
                    if guard.navigation_failure is not None:
                        raise self._with_browser_counts(
                            guard.navigation_failure,
                            blocked_popup_count,
                            blocked_download_count,
                        )
                    checkpoint, checkpoint_screenshot, visible_text, html = _capture_checkpoint(
                        page,
                        cdp_session=cdp_session,
                        elapsed_ms=prior_elapsed + 500,
                    )
                    checkpoints.append(checkpoint)
                    checkpoint_screenshots.append(checkpoint_screenshot)
                    prior_elapsed += 500
                title = page.title()
                html_bytes = len(html.encode("utf-8"))
                html_sha256 = hashlib.sha256(html.encode("utf-8")).hexdigest()
                screenshot = checkpoint_screenshots[-1]
                initial_screenshot = checkpoint_screenshots[0]
                image_dimensions = _image_dimensions(screenshot)
                initial_dimensions = _image_dimensions(initial_screenshot)
                deltas = _checkpoint_deltas(checkpoints)
                limitation_reasons: list[str] = []
                if deltas and deltas[-1].material_change:
                    limitation_reasons.append("rendering_changed_at_budget_end")
                final_checkpoint = checkpoints[-1]
                if _low_information(final_checkpoint):
                    limitation_reasons.append("low_information_capture")
                if _visual_dom_mismatch(final_checkpoint):
                    limitation_reasons.append("visual_dom_mismatch")
                html_persistable = html_bytes <= self.max_html_bytes
                html_omitted_reason = None
                if not html_persistable:
                    html_omitted_reason = "canonical_html_exceeds_5_mb_persistence_limit"
                    limitation_reasons.append(html_omitted_reason)
                full_page_screenshot, full_page_dimensions, full_page_reason = (
                    _bounded_full_page_screenshot(cdp_session, final_checkpoint)
                )
                if full_page_reason is not None:
                    limitation_reasons.append(full_page_reason)
                adequacy_blockers = {
                    "rendering_changed_at_budget_end",
                    "low_information_capture",
                    "visual_dom_mismatch",
                    "canonical_html_exceeds_5_mb_persistence_limit",
                }
                adequacy = (
                    CaptureAdequacy.LIMITED
                    if adequacy_blockers.intersection(limitation_reasons)
                    else CaptureAdequacy.ADEQUATE
                )
                response_headers = _sanitized_response_headers(response)
                readiness = CaptureReadiness(
                    checkpoint_schedule_ms=[item.elapsed_ms for item in checkpoints],
                    checkpoints=checkpoints,
                    deltas=deltas,
                    capture_adequacy=adequacy,
                    limitation_reasons=limitation_reasons,
                    canonical_checkpoint_ms=checkpoints[-1].elapsed_ms,
                    response_status=response.status,
                    response_url=response.url,
                    response_headers=response_headers,
                    content_type=content_type,
                    browser_version=browser_version,
                    collector_version=COLLECTOR_VERSION,
                    policy_version=CAPTURE_POLICY_VERSION,
                    network_route="application_validated_browser_dns",
                    initial_screenshot_changed=(
                        checkpoints[0].screenshot_sha256 != checkpoints[-1].screenshot_sha256
                    ),
                    html_bytes=html_bytes,
                    html_sha256=html_sha256,
                    html_omitted_reason=html_omitted_reason,
                    full_page_omitted_reason=full_page_reason,
                    blocked_resource_count=len(guard.blocked_requests),
                    popup_count=blocked_popup_count,
                    download_count=blocked_download_count,
                    generated_at=datetime.now(UTC),
                )
                semantic_elements = _semantic_element_snapshots(page)
                return CollectedPage(
                    final_url=final.normalized_url,
                    redirect_chain=redirect_chain,
                    redirects=redirects,
                    title=title,
                    html=html,
                    html_persistable=html_persistable,
                    visible_text=visible_text,
                    screenshot=screenshot,
                    initial_screenshot=(
                        initial_screenshot if readiness.initial_screenshot_changed else None
                    ),
                    full_page_screenshot=full_page_screenshot,
                    viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
                    image_dimensions=image_dimensions,
                    initial_image_dimensions=(
                        initial_dimensions if readiness.initial_screenshot_changed else None
                    ),
                    full_page_image_dimensions=full_page_dimensions,
                    collected_at=datetime.now(UTC),
                    content_type=content_type,
                    readiness=readiness,
                    semantic_elements=semantic_elements,
                    blocked_requests=guard.blocked_requests,
                    blocked_popup_count=blocked_popup_count,
                    blocked_download_count=blocked_download_count,
                )
            except UnsafeUrlError as error:
                raise self._error(
                    f"Unsafe navigation target blocked: {error}",
                    guard,
                    blocked_popup_count,
                    blocked_download_count,
                    reason_code="unsafe_destination",
                ) from error
            except PlaywrightError as error:
                if guard.navigation_failure is not None:
                    raise self._with_browser_counts(
                        guard.navigation_failure, blocked_popup_count, blocked_download_count
                    ) from error
                error_text = str(error).casefold()
                download_started = (
                    blocked_download_count > 0 or "download is starting" in error_text
                )
                unsupported_document = (
                    last_document_content_type is not None
                    and last_document_content_type not in ALLOWED_HTML_CONTENT_TYPES
                )
                reason_code = (
                    "timeout"
                    if "timeout" in error_text
                    else "unsupported_content_type"
                    if download_started or unsupported_document
                    else "navigation_error"
                )
                raise self._error(
                    f"Playwright navigation failed: {error}",
                    guard,
                    blocked_popup_count,
                    blocked_download_count,
                    reason_code=reason_code,
                ) from error
            finally:
                context.close()
                browser.close()

    def _require_html_response(
        self,
        response: Response,
        guard: _RequestGuard,
        blocked_popup_count: int,
        blocked_download_count: int,
    ) -> str:
        content_type = (
            (response.header_value("content-type") or "").split(";", maxsplit=1)[0].casefold()
        )
        if content_type not in ALLOWED_HTML_CONTENT_TYPES:
            raise self._error(
                f"Unsupported content type for collection: {content_type or 'missing'}",
                guard,
                blocked_popup_count,
                blocked_download_count,
                reason_code="unsupported_content_type",
            )
        return content_type

    @staticmethod
    def _with_browser_counts(
        error: CollectionError, blocked_popup_count: int, blocked_download_count: int
    ) -> CollectionError:
        return CollectionError(
            str(error),
            reason_code=error.reason_code,
            blocked_requests=error.blocked_requests,
            redirects=error.redirects,
            blocked_popup_count=blocked_popup_count,
            blocked_download_count=blocked_download_count,
        )

    @staticmethod
    def _error(
        message: str,
        guard: _RequestGuard,
        blocked_popup_count: int,
        blocked_download_count: int,
        *,
        reason_code: str = "navigation_error",
    ) -> CollectionError:
        return CollectionError(
            message,
            reason_code=reason_code,
            blocked_requests=guard.blocked_requests,
            redirects=guard.redirects,
            blocked_popup_count=blocked_popup_count,
            blocked_download_count=blocked_download_count,
        )


def _stop_page(page: Page) -> None:
    """Close the disposable page immediately after a response-policy violation."""

    try:
        page.close(run_before_unload=False)
    except PlaywrightError:
        return


def _redirect_records(request: Request, page: Page) -> list[RedirectRecord]:
    """Return redirect hops in source order, including status codes where available."""

    chain: list[Request] = []
    cursor: Request | None = request
    while cursor is not None:
        chain.append(cursor)
        cursor = cursor.redirected_from
    chain.reverse()
    records: list[RedirectRecord] = []
    for source, destination in zip(chain, chain[1:], strict=False):
        response = source.response()
        records.append(
            RedirectRecord(
                source_url=source.url,
                destination_url=destination.url,
                status_code=response.status if response is not None else None,
                raw_location=response.header_value("location") if response is not None else None,
                resource_type=source.resource_type,
                is_top_level_navigation=source.frame == page.main_frame,
            )
        )
    return records


def _image_dimensions(content: bytes) -> dict[str, int]:
    with Image.open(BytesIO(content)) as image:
        width, height = image.size
    return {"width": width, "height": height}


def _capture_checkpoint(
    page: Page, *, cdp_session: CDPSession, elapsed_ms: int
) -> tuple[CaptureCheckpoint, bytes, str, str]:
    """Measure browser-visible state and pixels without interacting with the document."""

    raw = page.evaluate(
        """() => {
            const root = document.documentElement;
            const body = document.body;
            const visibleText = (body?.innerText ?? "").replace(/\\s+/g, " ").trim();
            const all = Array.from(document.querySelectorAll("*"));
            const isVisible = (element) => {
                const style = getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return style.display !== "none" && style.visibility !== "hidden" &&
                    Number(style.opacity || "1") > 0 && rect.width > 0 && rect.height > 0;
            };
            const visible = all.filter(isVisible);
            const count = (selector) => Array.from(document.querySelectorAll(selector))
                .filter(isVisible).length;
            const width = Math.max(
                body?.scrollWidth ?? 0, root?.scrollWidth ?? 0,
                body?.offsetWidth ?? 0, root?.offsetWidth ?? 0
            );
            const height = Math.max(
                body?.scrollHeight ?? 0, root?.scrollHeight ?? 0,
                body?.offsetHeight ?? 0, root?.offsetHeight ?? 0
            );
            const html = root?.outerHTML ?? "";
            return {
                document_ready_state: document.readyState,
                html,
                html_bytes: new TextEncoder().encode(html).length,
                visible_text: visibleText,
                visible_text_chars: visibleText.length,
                visible_text_words: visibleText ? visibleText.split(/\\s+/).length : 0,
                element_count: all.length,
                visible_element_count: visible.length,
                visible_link_count: count("a[href]"),
                visible_button_count: count("button, [role=button]"),
                visible_input_count: count("input, select, textarea"),
                visible_image_count: count("img, svg"),
                visible_iframe_count: count("iframe"),
                visible_canvas_count: count("canvas"),
                document_width: width,
                document_height: height
            };
        }"""
    )
    if not isinstance(raw, dict):
        raise CollectionError("Capture checkpoint did not return a metrics object")
    screenshot = _capture_cdp_png(cdp_session, capture_beyond_viewport=False)
    image_dimensions = _image_dimensions(screenshot)
    entropy, tile_ratio = _visual_information(screenshot)
    visible_text = str(raw.get("visible_text", ""))
    html = str(raw.get("html", ""))
    checkpoint = CaptureCheckpoint(
        elapsed_ms=elapsed_ms,
        captured_at=datetime.now(UTC),
        document_ready_state=str(raw.get("document_ready_state", "unknown")),
        html_bytes=_bounded_int(raw.get("html_bytes")),
        visible_text_chars=_bounded_int(raw.get("visible_text_chars")),
        visible_text_words=_bounded_int(raw.get("visible_text_words")),
        element_count=_bounded_int(raw.get("element_count")),
        visible_element_count=_bounded_int(raw.get("visible_element_count")),
        visible_link_count=_bounded_int(raw.get("visible_link_count")),
        visible_button_count=_bounded_int(raw.get("visible_button_count")),
        visible_input_count=_bounded_int(raw.get("visible_input_count")),
        visible_image_count=_bounded_int(raw.get("visible_image_count")),
        visible_iframe_count=_bounded_int(raw.get("visible_iframe_count")),
        visible_canvas_count=_bounded_int(raw.get("visible_canvas_count")),
        document_width=_bounded_int(raw.get("document_width")),
        document_height=_bounded_int(raw.get("document_height")),
        screenshot_sha256=hashlib.sha256(screenshot).hexdigest(),
        screenshot_bytes=len(screenshot),
        screenshot_width=image_dimensions["width"],
        screenshot_height=image_dimensions["height"],
        screenshot_entropy=entropy,
        informative_tile_ratio=tile_ratio,
    )
    return checkpoint, screenshot, visible_text, html


def _checkpoint_deltas(checkpoints: list[CaptureCheckpoint]) -> list[CaptureCheckpointDelta]:
    deltas: list[CaptureCheckpointDelta] = []
    for previous, current in zip(checkpoints, checkpoints[1:], strict=False):
        screenshot_changed = previous.screenshot_sha256 != current.screenshot_sha256
        html_delta = current.html_bytes - previous.html_bytes
        text_delta = current.visible_text_chars - previous.visible_text_chars
        visible_delta = current.visible_element_count - previous.visible_element_count
        height_delta = current.document_height - previous.document_height
        informative_delta = current.informative_tile_ratio - previous.informative_tile_ratio
        material = any(
            (
                abs(html_delta) >= 32,
                abs(text_delta) >= 4,
                abs(visible_delta) >= 1,
                abs(height_delta) >= 8,
                screenshot_changed,
            )
        )
        deltas.append(
            CaptureCheckpointDelta(
                from_elapsed_ms=previous.elapsed_ms,
                to_elapsed_ms=current.elapsed_ms,
                html_bytes_delta=html_delta,
                visible_text_chars_delta=text_delta,
                visible_element_count_delta=visible_delta,
                visible_link_count_delta=current.visible_link_count - previous.visible_link_count,
                visible_image_count_delta=(
                    current.visible_image_count - previous.visible_image_count
                ),
                document_height_delta=height_delta,
                screenshot_changed=screenshot_changed,
                informative_tile_ratio_delta=informative_delta,
                material_change=material,
            )
        )
    return deltas


def _low_information(checkpoint: CaptureCheckpoint) -> bool:
    return (
        checkpoint.visible_text_chars < 24
        and checkpoint.visible_link_count == 0
        and checkpoint.visible_image_count == 0
        and checkpoint.visible_iframe_count == 0
        and checkpoint.visible_canvas_count == 0
        and checkpoint.informative_tile_ratio < 0.01
    )


def _visual_dom_mismatch(checkpoint: CaptureCheckpoint) -> bool:
    """Flag DOM text that is not credibly represented in the viewport pixels.

    ``innerText`` alone cannot detect an opaque splash or challenge layer covering an
    otherwise rich document.  The two bounded thresholds deliberately require either
    a nearly uniform viewport or a large amount of text paired with very little visual
    variation.  Canvas/image-heavy pages remain eligible because this check only
    applies when the DOM claims meaningful text is visible.
    """

    return (checkpoint.visible_text_chars >= 80 and checkpoint.informative_tile_ratio < 0.01) or (
        checkpoint.visible_text_chars >= 1_000 and checkpoint.informative_tile_ratio < 0.10
    )


def _bounded_full_page_screenshot(
    cdp_session: CDPSession, checkpoint: CaptureCheckpoint
) -> tuple[bytes | None, dict[str, int] | None, str | None]:
    capture_height = max(1, min(checkpoint.document_height, MAX_FULL_PAGE_HEIGHT))
    capture_width = max(1, min(checkpoint.document_width, VIEWPORT_WIDTH))
    reason = (
        "full_page_truncated_at_12000_px"
        if checkpoint.document_height > MAX_FULL_PAGE_HEIGHT
        else None
    )
    try:
        content = _capture_cdp_png(
            cdp_session,
            capture_beyond_viewport=True,
            clip={
                "x": 0,
                "y": 0,
                "width": capture_width,
                "height": capture_height,
                "scale": 1,
            },
        )
    except (PlaywrightError, ValueError):
        return None, None, "bounded_full_page_screenshot_failed"
    return content, _image_dimensions(content), reason


def _capture_cdp_png(
    cdp_session: CDPSession,
    *,
    capture_beyond_viewport: bool,
    clip: dict[str, int] | None = None,
) -> bytes:
    """Capture Chromium pixels without Playwright's unbounded web-font readiness wait."""

    parameters: dict[str, object] = {
        "format": "png",
        "fromSurface": True,
        "captureBeyondViewport": capture_beyond_viewport,
    }
    if clip is not None:
        parameters["clip"] = clip
    payload = cdp_session.send("Page.captureScreenshot", parameters)
    encoded = payload.get("data")
    if not isinstance(encoded, str):
        raise ValueError("Chromium screenshot response did not contain PNG data")
    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("Chromium screenshot response contained invalid base64") from error
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Chromium screenshot response was not a PNG")
    return content


def _visual_information(content: bytes) -> tuple[float, float]:
    """Return normalized grayscale entropy and the ratio of non-uniform 64px tiles."""

    with Image.open(BytesIO(content)) as image:
        gray = image.convert("L")
        histogram = gray.histogram()
        pixels = max(1, gray.width * gray.height)
        entropy_bits = -sum(
            (count / pixels) * math.log2(count / pixels) for count in histogram if count
        )
        informative = 0
        total = 0
        for top in range(0, gray.height, 64):
            for left in range(0, gray.width, 64):
                tile = gray.crop(
                    (left, top, min(left + 64, gray.width), min(top + 64, gray.height))
                )
                extrema = tile.getextrema()
                total += 1
                if (
                    isinstance(extrema, tuple)
                    and len(extrema) == 2
                    and isinstance(extrema[0], (int, float))
                    and isinstance(extrema[1], (int, float))
                    and extrema[1] - extrema[0] >= 12
                ):
                    informative += 1
    return round(entropy_bits / 8.0, 6), round(informative / max(1, total), 6)


def _sanitized_response_headers(response: Response) -> dict[str, str]:
    allowed = {
        "cache-control",
        "content-language",
        "content-length",
        "content-type",
        "date",
        "etag",
        "last-modified",
        "location",
        "server",
        "x-robots-tag",
    }
    # Playwright's type surface declares string values, but Chromium can expose a null-valued
    # response header on real redirects/restriction pages. Treat it as absent instead of allowing
    # one malformed header to erase the entire capture.
    raw_headers: dict[str, object] = dict(response.all_headers())
    return {
        key.casefold(): value[:1000]
        for key, value in raw_headers.items()
        if key.casefold() in allowed and isinstance(value, str)
    }


def _bounded_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return max(0, int(value))
    return 0


def _bounded_scroll_discovery(page: Page) -> bool:
    """Trigger light-DOM lazy rendering at three read-only positions, then restore the top."""

    dimensions = page.evaluate(
        """() => ({
            height: Math.max(document.body?.scrollHeight || 0,
                document.documentElement?.scrollHeight || 0),
            viewport: innerHeight
        })"""
    )
    if not isinstance(dimensions, dict):
        return False
    height = _bounded_int(dimensions.get("height"))
    viewport = _bounded_int(dimensions.get("viewport"))
    if viewport <= 0 or height <= viewport + 80:
        return False
    maximum = max(0, height - viewport)
    for position in (maximum // 2, maximum):
        page.evaluate(
            "position => scrollTo({top: position, left: 0, behavior: 'instant'})", position
        )
        page.wait_for_timeout(150)
    page.evaluate("() => scrollTo({top: 0, left: 0, behavior: 'instant'})")
    page.wait_for_timeout(150)
    return True


def _semantic_element_snapshots(page: Page) -> list[SemanticElementSnapshot]:
    """Map visible light DOM, open shadow roots, and readable same-origin iframe elements."""

    raw = page.evaluate(
        """() => {
            const selectorFor = (element) => {
                const parts = [];
                let current = element;
                while (current && current.nodeType === Node.ELEMENT_NODE && parts.length < 8) {
                    let part = current.tagName.toLowerCase();
                    if (current.id && /^[A-Za-z][A-Za-z0-9_-]{0,80}$/.test(current.id)) {
                        part += `#${CSS.escape(current.id)}`;
                        parts.unshift(part);
                        break;
                    }
                    const parent = current.parentElement;
                    if (parent) {
                        const siblings = Array.from(parent.children)
                            .filter((sibling) => sibling.tagName === current.tagName);
                        if (siblings.length > 1) {
                            part += `:nth-of-type(${siblings.indexOf(current) + 1})`;
                        }
                    }
                    parts.unshift(part);
                    current = parent;
                }
                return parts.join(" > ");
            };
            const roots = [{root: document, context: "document", prefix: ""}];
            const candidates = [];
            const visited = new Set();
            while (roots.length && candidates.length < 300) {
                const entry = roots.shift();
                if (!entry || visited.has(entry.root)) continue;
                visited.add(entry.root);
                const all = Array.from(entry.root.querySelectorAll("*"));
                for (const element of all) {
                    if (element.shadowRoot) {
                        roots.push({root: element.shadowRoot, context: "open_shadow_root",
                            prefix: `${entry.prefix}shadow:`});
                    }
                    if (element instanceof HTMLIFrameElement) {
                        try {
                            if (element.contentDocument) {
                                roots.push({root: element.contentDocument,
                                    context: "same_origin_iframe",
                                    prefix: `${entry.prefix}iframe:`});
                            }
                        } catch (_) {
                            // Cross-origin frames remain opaque by browser policy.
                        }
                    }
                    if (element.matches(
                        "a[href], h1, h2, [data-brand], [itemprop], address, strong, button"
                    )) candidates.push({element, context: entry.context, prefix: entry.prefix});
                    if (candidates.length >= 300) break;
                }
            }
            return candidates.flatMap(({element, context, prefix}) => {
                const style = getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                if (style.display === "none" || style.visibility === "hidden" ||
                    Number(style.opacity || "1") <= 0 || rect.width <= 0 || rect.height <= 0 ||
                    rect.right <= 0 || rect.bottom <= 0 || rect.left >= innerWidth ||
                    rect.top >= innerHeight) {
                    return [];
                }
                const text = (element.innerText || element.textContent || "")
                    .replace(/\\s+/g, " ").trim().slice(0, 500);
                return [{
                    selector: `${prefix}${selectorFor(element)}`,
                    tag: element.tagName.toLowerCase(),
                    role: element.getAttribute("role"),
                    accessible_name: (element.getAttribute("aria-label") || text).slice(0, 200),
                    visible_text: text,
                    href: element instanceof HTMLAnchorElement ? element.href : null,
                    source_context: context,
                    x: Math.max(0, rect.x),
                    y: Math.max(0, rect.y),
                    width: Math.min(rect.width, innerWidth - Math.max(0, rect.x)),
                    height: Math.min(rect.height, innerHeight - Math.max(0, rect.y))
                }];
            });
        }"""
    )
    if not isinstance(raw, list):
        return []
    snapshots: list[SemanticElementSnapshot] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            snapshots.append(SemanticElementSnapshot.model_validate(item))
        except ValueError:
            continue
    return snapshots
