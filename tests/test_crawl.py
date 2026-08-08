"""Fixture coverage for the bounded, deterministic Engine V0.1 crawler."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from hawkeye.collector.safety import SafetyPolicy
from hawkeye.crawl import DiscoveredLink, crawl_frontier_priority, normalize_crawl_url
from hawkeye.models import InvestigationResult, SemanticElementSnapshot
from hawkeye.pipeline import _sorted_links, investigate


def _loopback_policy(
    resolver: Callable[[str, int], list[str]] | None = None,
) -> SafetyPolicy:
    return SafetyPolicy(
        resolver=resolver or (lambda _host, _port: ["127.0.0.1"]),
        allow_loopback_for_testing=True,
    )


def _crawl(
    url: str,
    output: Path,
    *,
    policy: SafetyPolicy | None = None,
    timeout_seconds: float = 15.0,
    max_pages: int = 5,
    max_depth: int = 1,
    **extra: int,
) -> InvestigationResult:
    return investigate(
        url,
        output=output,
        timeout_seconds=timeout_seconds,
        case_timeout_seconds=30.0,
        max_pages=max_pages,
        max_depth=max_depth,
        safety_policy=policy or _loopback_policy(),
        **extra,
    )


def test_bfs_child_has_exact_parent_evidence_and_depth_limit(
    fixture_server_url: str, tmp_path: Path
) -> None:
    result = _crawl(f"{fixture_server_url}crawl-cycle-root", tmp_path / "cases")

    assert result.case.status == "completed"
    assert result.case.page_count == 2
    root, child = result.pages
    assert root.id == "page-001"
    assert child.id == "page-002"
    assert child.depth == 1
    assert child.parent_page_id == root.id
    assert child.source_evidence_id == "evidence-page-001"
    assert child.discovery_method == "html_anchor"
    assert child.state == "completed"
    assert any(record.skip_reason == "depth_limit" for record in result.frontier)

    graph = json.loads((Path(result.case_directory) / "graph.json").read_text(encoding="utf-8"))
    discovery_edges = [edge for edge in graph["edges"] if edge["type"] == "discovered_via_link"]
    assert len(discovery_edges) == 1
    edge = discovery_edges[0]
    assert edge["source"] == "page:page-001"
    assert edge["target"] == "page:page-002"
    assert edge["evidence_id"] == "evidence-page-001"
    assert edge["extraction_method"] == "html_anchor"
    assert edge["attributes"]["crawl_depth"] == 1
    assert edge["attributes"]["original_href"] == "/crawl-cycle-child"


def test_browser_semantic_frontier_includes_open_shadow_and_same_origin_frame_links() -> None:
    snapshots = [
        SemanticElementSnapshot(
            selector="shadow:a#contact",
            tag="a",
            accessible_name="Contact",
            visible_text="Contact",
            href="https://example.test/contact",
            source_context="open_shadow_root",
            x=10,
            y=10,
            width=80,
            height=20,
        ),
        SemanticElementSnapshot(
            selector="iframe:a#help",
            tag="a",
            accessible_name="Help",
            visible_text="Help",
            href="https://example.test/help",
            source_context="same_origin_iframe",
            x=10,
            y=40,
            width=80,
            height=20,
        ),
    ]

    links = _sorted_links("<main>No light-DOM anchors</main>", "https://example.test", snapshots)

    assert [item.normalized_url for item in links] == [
        "https://example.test/contact",
        "https://example.test/help",
    ]
    assert all(item.discovery_method == "browser_semantic" for item in links)


def test_normalizes_fragments_tracking_parameters_and_query_order_deterministically(
    fixture_server_url: str, tmp_path: Path
) -> None:
    expected = f"{fixture_server_url}crawl-child?a=1&b=2"
    assert (
        normalize_crawl_url(
            "/crawl-child/?b=2&a=1&utm_campaign=fixture#fragment", fixture_server_url
        )
        == expected
    )

    result = _crawl(f"{fixture_server_url}crawl-variants", tmp_path / "cases")

    assert result.case.page_count == 2
    assert result.pages[1].normalized_url == expected
    assert sum(record.skip_reason == "duplicate_url" for record in result.frontier) == 2


def test_canonical_final_url_prevents_fragment_only_self_links_from_being_crawled(
    fixture_server_url: str, tmp_path: Path
) -> None:
    result = _crawl(f"{fixture_server_url}crawl-self-fragment", tmp_path / "cases")

    assert result.case.page_count == 2
    assert result.pages[1].normalized_url.endswith("/crawl-child")
    assert any(
        record.original_href == "#current" and record.skip_reason == "duplicate_url"
        for record in result.frontier
    )


def test_enforces_five_page_budget_in_sorted_bfs_order(
    fixture_server_url: str, tmp_path: Path
) -> None:
    result = _crawl(f"{fixture_server_url}crawl-budget", tmp_path / "cases")

    assert result.case.page_count == 5
    assert [page.normalized_url.rsplit("/", maxsplit=1)[-1] for page in result.pages[1:]] == [
        "budget-1",
        "budget-2",
        "budget-3",
        "budget-4",
    ]
    assert sum(record.skip_reason == "page_budget" for record in result.frontier) == 3


def test_frontier_ranking_prefers_public_contact_and_information_routes() -> None:
    links = [
        DiscoveredLink("/promo", "https://example.test/promo", "Bonus event"),
        DiscoveredLink("/about", "https://example.test/about", "About company"),
        DiscoveredLink("/contact", "https://example.test/contact", "Hubungi Kami"),
        DiscoveredLink("/games", "https://example.test/games", "Games"),
    ]

    ranked = sorted(links, key=crawl_frontier_priority)

    assert [item.anchor_text for item in ranked] == [
        "Hubungi Kami",
        "About company",
        "Games",
        "Bonus event",
    ]
    assert crawl_frontier_priority(ranked[0]) == (0, "contact")


def test_external_redirect_is_recorded_as_failed_child_and_never_followed(
    fixture_server_url: str, tmp_path: Path
) -> None:
    def resolver(host: str, _port: int) -> list[str]:
        return ["93.184.216.34"] if host == "outside.example.net" else ["127.0.0.1"]

    result = _crawl(
        f"{fixture_server_url}crawl-external-redirect-root",
        tmp_path / "cases",
        policy=_loopback_policy(resolver),
    )

    assert result.case.status == "completed"
    child = result.pages[1]
    assert child.state == "failed"
    assert child.skip_reason == "external_host"
    assert child.navigation_status == "blocked_by_policy"
    assert any(
        blocked.is_navigation and "outside.example.net" in blocked.url
        for blocked in child.blocked_requests
    )
    redirect_frontier = [
        record for record in result.frontier if record.discovery_method == "redirect"
    ]
    assert len(redirect_frontier) == 1
    assert redirect_frontier[0].skip_reason == "external_host"
    assert redirect_frontier[0].source_evidence_id == child.redirect_evidence_id
    assert redirect_frontier[0].normalized_url == "https://outside.example.net/remote"
    evidence = json.loads(
        (Path(result.case_directory) / "evidence.json").read_text(encoding="utf-8")
    )
    assert any(record["id"] == child.redirect_evidence_id for record in evidence)
    assert result.candidates[0].hostname == "outside.example.net"
    assert result.candidates[0].discovery_priority_score == 30


def test_private_subresource_is_aborted_before_network_dispatch(
    fixture_server_url: str, tmp_path: Path
) -> None:
    def resolver(host: str, _port: int) -> list[str]:
        return ["192.168.1.1"] if host == "private.resource.test" else ["127.0.0.1"]

    result = _crawl(
        f"{fixture_server_url}crawl-private-resource",
        tmp_path / "cases",
        policy=_loopback_policy(resolver),
        max_pages=1,
        max_depth=0,
    )

    page = result.pages[0]
    assert page.state == "completed"
    assert page.blocked_requests
    assert any(
        request.resource_type == "script"
        and request.reason.startswith("unsafe_destination")
        and "private.resource.test" in request.url
        for request in page.blocked_requests
    )


def test_case_shared_request_and_declared_response_budgets_stop_resource_explosions(
    fixture_server_url: str, tmp_path: Path
) -> None:
    request_limited = _crawl(
        f"{fixture_server_url}crawl-request-budget",
        tmp_path / "request-budget-cases",
        max_pages=1,
        max_depth=0,
        max_total_requests=2,
    )
    response_limited = _crawl(
        f"{fixture_server_url}crawl-response-budget",
        tmp_path / "response-budget-cases",
        max_pages=1,
        max_depth=0,
        max_declared_response_bytes=1_000,
    )

    assert request_limited.case.budget_exhausted_reason == "request_budget"
    assert request_limited.case.total_request_count > 2
    assert request_limited.pages[0].state == "failed"
    assert response_limited.case.budget_exhausted_reason == "response_budget"
    assert response_limited.case.total_declared_response_bytes > 1_000
    assert response_limited.pages[0].state == "failed"


def test_popup_and_download_attempts_are_not_permitted(
    fixture_server_url: str, tmp_path: Path
) -> None:
    popup_result = _crawl(
        f"{fixture_server_url}crawl-popup",
        tmp_path / "popup-cases",
        max_pages=1,
        max_depth=0,
    )
    download_result = _crawl(
        f"{fixture_server_url}crawl-download",
        tmp_path / "download-cases",
        max_pages=1,
        max_depth=0,
    )

    assert popup_result.pages[0].blocked_popup_count >= 1
    assert download_result.pages[0].blocked_download_count >= 1


def test_non_html_child_and_timeout_do_not_fail_the_whole_case(
    fixture_server_url: str, tmp_path: Path
) -> None:
    non_html = _crawl(f"{fixture_server_url}crawl-non-html-root", tmp_path / "non-html-cases")
    timeout = _crawl(
        f"{fixture_server_url}crawl-timeout-root",
        tmp_path / "timeout-cases",
        timeout_seconds=0.2,
    )

    assert non_html.case.status == "completed"
    assert non_html.pages[1].state == "failed"
    assert non_html.pages[1].skip_reason == "unsupported_content_type"
    assert timeout.case.status == "completed"
    assert timeout.pages[1].navigation_status == "timed_out"
    assert timeout.pages[2].state == "completed"


def test_unusable_page_does_not_expand_frontier_but_records_the_decision(
    fixture_server_url: str, tmp_path: Path
) -> None:
    result = _crawl(f"{fixture_server_url}crawl-unusable-root", tmp_path / "cases")

    assert result.case.status == "completed"
    assert result.case.page_count == 1
    assert len(result.pages) == 1
    assert any(record.skip_reason == "unusable_parent_page" for record in result.frontier)


def test_canonical_seed_redirect_allows_only_seed_and_final_exact_hosts(
    fixture_server_url: str, tmp_path: Path
) -> None:
    result = _crawl(f"{fixture_server_url}canonical-redirect", tmp_path / "cases")

    assert result.case.status == "completed"
    assert set(result.case.allowed_crawl_hosts) == {"127.0.0.1", "localhost"}
    assert result.case.page_count == 2
    assert result.pages[1].state == "completed"
    assert result.pages[1].normalized_url.startswith("http://127.0.0.1:")


def test_identical_child_content_is_observable_but_marked_to_prevent_reexpansion(
    fixture_server_url: str, tmp_path: Path
) -> None:
    result = _crawl(f"{fixture_server_url}same-content-root", tmp_path / "cases")

    assert result.case.status == "completed"
    assert result.case.page_count == 3
    assert result.pages[1].state == "completed"
    assert result.pages[2].state == "completed"
    assert result.pages[2].duplicate_of_page_id == result.pages[1].id
    assert result.pages[2].skip_reason == "duplicate_content"
