"""One-page Playwright collection with request-by-request safety revalidation."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from io import BytesIO
from urllib.parse import urljoin

from PIL import Image
from playwright.sync_api import (
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

from hawkeye.models import BlockedRequestRecord, CollectedPage, RedirectRecord

from .safety import SafetyPolicy, UnsafeUrlError

VIEWPORT_WIDTH = 1440
VIEWPORT_HEIGHT = 1024
DEFAULT_VIEWPORT: ViewportSize = {"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}
DEFAULT_USER_AGENT = "JudolGraph-HAWKEYE/0.2 (+public-evidence-collection)"
ALLOWED_HTML_CONTENT_TYPES = frozenset({"text/html", "application/xhtml+xml"})
MAX_BLOCKED_REQUEST_RECORDS = 100
DEFAULT_MAX_TOTAL_REQUESTS = 200
DEFAULT_MAX_DECLARED_RESPONSE_BYTES = 10_000_000


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
        is_navigation = request.is_navigation_request()
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
                else self.safety.validate_url(request.url, refresh_dns=True)
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
        max_html_bytes: int = 2_000_000,
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
        """Navigate once, preserve HTML and one screenshot, then close all browser resources."""

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
            browser = playwright.chromium.launch(headless=not self.headed)
            context = browser.new_context(
                user_agent=self.user_agent,
                viewport=DEFAULT_VIEWPORT,
                accept_downloads=False,
                service_workers="block",
            )
            context.route("**/*", guard.handle)
            context.route_web_socket("**/*", guard.handle_websocket)
            page = context.new_page()
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
                    _stop_page(page)

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
                title = page.title()
                html = page.content()
                html_bytes = len(html.encode("utf-8"))
                if html_bytes > self.max_html_bytes:
                    raise self._error(
                        "Rendered HTML exceeds "
                        f"{self.max_html_bytes} byte limit ({html_bytes} bytes)",
                        guard,
                        blocked_popup_count,
                        blocked_download_count,
                        reason_code="response_too_large",
                    )
                screenshot = page.screenshot(type="png", full_page=False, timeout=timeout_ms)
                image_dimensions = _image_dimensions(screenshot)
                return CollectedPage(
                    final_url=final.normalized_url,
                    redirect_chain=redirect_chain,
                    redirects=redirects,
                    title=title,
                    html=html,
                    screenshot=screenshot,
                    viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
                    image_dimensions=image_dimensions,
                    collected_at=datetime.now(UTC),
                    content_type=content_type,
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
                reason_code = (
                    "timeout"
                    if "timeout" in error_text
                    else "unsupported_content_type"
                    if "download is starting" in error_text
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
        content_length = response.header_value("content-length")
        if content_length is not None:
            try:
                declared_bytes = int(content_length)
            except ValueError:
                declared_bytes = 0
            if declared_bytes > self.max_html_bytes:
                raise self._error(
                    f"Response exceeds {self.max_html_bytes} byte limit ({declared_bytes} bytes)",
                    guard,
                    blocked_popup_count,
                    blocked_download_count,
                    reason_code="response_too_large",
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
