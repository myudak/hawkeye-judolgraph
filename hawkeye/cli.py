"""Command-line interface for single investigations and the fixed smoke matrix."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path

from hawkeye.collector.safety import SafetyPolicy, UnsafeUrlError
from hawkeye.comparison import ComparisonInputError, compare_cases, write_comparison
from hawkeye.demo import build_demo
from hawkeye.diagnostics import DiagnosticInputError, run_render_diagnostics
from hawkeye.discovery import (
    ExternalDiscoveryInputError,
    ExternalDiscoverySourceError,
    UrlscanPublicSearchSource,
    discover_case,
)
from hawkeye.evaluation import EvaluationInputError, evaluate_case
from hawkeye.pipeline import investigate
from hawkeye.review_app import run_local_server
from hawkeye.review_app.loader import CaseIntegrityError
from hawkeye.smoke import run_live_smoke


def build_parser() -> argparse.ArgumentParser:
    """Create the bounded Engine V1 command surface."""

    parser = argparse.ArgumentParser(prog="hawkeye", description="JudolGraph Engine V1")
    subcommands = parser.add_subparsers(dest="command", required=True)

    investigate_parser = subcommands.add_parser(
        "investigate", help="Collect a bounded same-site evidence graph from one public seed URL"
    )
    investigate_parser.add_argument("seed_url", help="Public http(s) seed URL")
    investigate_parser.add_argument(
        "--output", type=Path, default=Path("cases"), help="Case output root"
    )
    investigate_parser.add_argument(
        "--timeout", type=float, default=30.0, help="Navigation timeout in seconds"
    )
    investigate_parser.add_argument(
        "--headed", action="store_true", help="Show the fresh browser window"
    )
    investigate_parser.add_argument("--case-id", help="Optional filesystem-safe case identifier")
    investigate_parser.add_argument(
        "--max-redirects", type=int, default=5, help="Maximum redirect hops (default: 5)"
    )
    investigate_parser.add_argument(
        "--max-pages", type=int, choices=range(1, 6), default=5, help="HTML page cap (1-5)"
    )
    investigate_parser.add_argument(
        "--max-depth", type=int, choices=(0, 1), default=1, help="Same-site BFS depth (0-1)"
    )
    investigate_parser.add_argument(
        "--case-timeout",
        type=float,
        default=120.0,
        help="Whole-case timeout in seconds (hard maximum: 120)",
    )
    investigate_parser.add_argument("--user-agent", help="Optional browser user-agent override")
    investigate_parser.add_argument(
        "--corpus",
        type=Path,
        help=(
            "Optional local completed-case corpus root for shared-signal candidate generation; "
            "candidates are never crawled"
        ),
    )
    investigate_parser.add_argument(
        "--allow-loopback-for-testing",
        action="store_true",
        help="Permit loopback only for local fixture tests; never permits other private targets",
    )

    smoke_parser = subcommands.add_parser(
        "smoke-test", help="Run the bounded fixed ten-domain live robustness matrix"
    )
    smoke_parser.add_argument(
        "--output", type=Path, default=Path("live-smoke-tests"), help="Smoke-test output root"
    )

    compare_parser = subcommands.add_parser(
        "compare", help="Compare two already-collected local cases without network access"
    )
    compare_parser.add_argument("left_case", type=Path, help="First completed case directory")
    compare_parser.add_argument("right_case", type=Path, help="Second completed case directory")
    compare_parser.add_argument(
        "--output", type=Path, required=True, help="New comparison.json output path"
    )

    discover_parser = subcommands.add_parser(
        "discover",
        help=(
            "Query one bounded public-source strategy for a completed case; returned leads are "
            "never crawled automatically"
        ),
    )
    discover_parser.add_argument(
        "case_directory", type=Path, help="Completed local case directory to use as the query seed"
    )

    evaluate_parser = subcommands.add_parser(
        "evaluate",
        help=(
            "Assess one completed local case against a checked-in evaluation manifest "
            "without network access"
        ),
    )
    evaluate_parser.add_argument("manifest", type=Path, help="Evaluation manifest JSON")
    evaluate_parser.add_argument(
        "case_directory", type=Path, help="Completed local case directory to assess"
    )
    evaluate_parser.add_argument(
        "--report", type=Path, required=True, help="New report JSON output path"
    )

    diagnose_parser = subcommands.add_parser(
        "diagnose",
        help=(
            "Create fixed-time render diagnostics for a completed case page without changing "
            "canonical evidence"
        ),
    )
    diagnose_parser.add_argument("case_directory", type=Path, help="Completed local case directory")
    diagnose_parser.add_argument(
        "--page-id", default="page-001", help="Verified case page ID to measure (default: page-001)"
    )
    diagnose_parser.add_argument(
        "--mode", choices=("fixture", "live"), required=True, help="Diagnostic provenance label"
    )
    diagnose_parser.add_argument(
        "--timeout", type=float, default=30.0, help="Navigation timeout in seconds"
    )
    diagnose_parser.add_argument(
        "--allow-loopback-for-testing",
        action="store_true",
        help="Permit loopback only for deterministic local diagnostic fixtures",
    )
    discover_parser.add_argument(
        "--source", choices=("urlscan-public",), default="urlscan-public", help="Public source"
    )
    discover_parser.add_argument(
        "--output", type=Path, required=True, help="New external-discovery output directory"
    )
    discover_parser.add_argument(
        "--limit", type=int, default=10, help="Maximum source result rows to evaluate (1-20)"
    )
    discover_parser.add_argument(
        "--timeout", type=float, default=10.0, help="External source timeout in seconds (max: 10)"
    )
    discover_parser.add_argument(
        "--urlscan-api-key", help="Optional urlscan.io API key; it is not persisted or printed"
    )
    discover_parser.add_argument(
        "--response-file",
        type=Path,
        help=(
            "Replay one saved urlscan search JSON response for deterministic tests or local review"
        ),
    )

    serve_parser = subcommands.add_parser(
        "serve",
        help="Run the local-only, read-only investigator console on 127.0.0.1",
    )
    serve_parser.add_argument(
        "--cases", type=Path, default=Path("cases"), help="Local case-package root"
    )
    serve_parser.add_argument(
        "--comparisons",
        type=Path,
        help=(
            "Optional separate local directory of verified offline comparison JSON documents; "
            "never writes or fetches"
        ),
    )
    serve_parser.add_argument(
        "--port", type=int, default=8760, help="Local loopback port (1024-65535)"
    )

    demo_parser = subcommands.add_parser(
        "demo",
        help=(
            "Write a new sanitized offline Gemastik demo corpus; never fetches, collects, or "
            "overwrites"
        ),
    )
    demo_parser.add_argument(
        "--output",
        type=Path,
        default=Path("verification-output/gemastik-demo"),
        help="New demo output directory; it must not already exist",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run a command and return a conventional process exit code."""

    args = build_parser().parse_args(argv)
    if args.command == "investigate":
        return _run_investigate(args)
    if args.command == "smoke-test":
        summary = run_live_smoke(args.output)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.command == "compare":
        return _run_compare(args)
    if args.command == "discover":
        return _run_discover(args)
    if args.command == "evaluate":
        return _run_evaluate(args)
    if args.command == "diagnose":
        return _run_diagnose(args)
    if args.command == "serve":
        return _run_serve(args)
    if args.command == "demo":
        return _run_demo(args)
    raise AssertionError(f"Unexpected command: {args.command}")


def _run_investigate(args: argparse.Namespace) -> int:
    if args.allow_loopback_for_testing and os.environ.get("HAWKEYE_TEST_MODE") != "1":
        print(
            json.dumps(
                {
                    "status": "rejected",
                    "error": (
                        "--allow-loopback-for-testing requires HAWKEYE_TEST_MODE=1 and is only "
                        "intended for deterministic local fixtures"
                    ),
                },
                indent=2,
            )
        )
        return 2
    safety = SafetyPolicy(allow_loopback_for_testing=args.allow_loopback_for_testing)
    try:
        result = investigate(
            args.seed_url,
            output=args.output,
            timeout_seconds=args.timeout,
            case_timeout_seconds=args.case_timeout,
            max_pages=args.max_pages,
            max_depth=args.max_depth,
            headed=args.headed,
            case_id=args.case_id,
            max_redirects=args.max_redirects,
            user_agent=args.user_agent,
            safety_policy=safety,
            corpus_root=args.corpus,
        )
    except (UnsafeUrlError, ValueError) as error:
        print(json.dumps({"status": "rejected", "error": str(error)}, indent=2))
        return 2
    summary = {
        "case_directory": result.case_directory,
        "case_id": result.case.case_id,
        "error": result.case.error,
        "final_url": result.case.final_url,
        "navigation_status": result.case.navigation_status,
        "capture_outcome": result.case.capture_outcome,
        "content_usable": result.case.content_usable,
        "page_count": result.case.page_count,
        "candidate_count": result.case.candidate_count,
        "allowed_crawl_hosts": result.case.allowed_crawl_hosts,
        "status": result.case.status,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if result.case.status == "completed" else 1


def _run_compare(args: argparse.Namespace) -> int:
    try:
        document = compare_cases(args.left_case, args.right_case)
        output_path = write_comparison(document, args.output)
    except (ComparisonInputError, FileExistsError, ValueError) as error:
        print(json.dumps({"status": "rejected", "error": str(error)}, indent=2))
        return 2
    summary = {
        "status": "completed",
        "comparison_path": str(output_path),
        "left_case_id": document.left_case_id,
        "right_case_id": document.right_case_id,
        "review_status": document.review_status,
        "candidate_mirror_score": document.candidate_mirror_score,
        "components": {
            component.name: {
                "score": component.score,
                "available": component.available,
                "status": component.status,
            }
            for component in document.components
        },
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _run_discover(args: argparse.Namespace) -> int:
    """Run the single V0.4 source adapter without any candidate navigation."""

    try:
        source = UrlscanPublicSearchSource(
            api_key=args.urlscan_api_key,
            response_file=args.response_file,
        )
        result = discover_case(
            args.case_directory,
            output_directory=args.output,
            source=source,
            limit=args.limit,
            timeout_seconds=args.timeout,
        )
    except (
        ExternalDiscoveryInputError,
        ExternalDiscoverySourceError,
        FileExistsError,
        ValueError,
    ) as error:
        print(json.dumps({"status": "rejected", "error": str(error)}, indent=2))
        return 2
    document = result.document
    summary = {
        "status": "completed",
        "discovery_directory": str(result.directory),
        "source_name": document.source_name,
        "source_case_id": document.source_case_id,
        "query_hostname": document.query_hostname,
        "source_result_count": document.source_result_count,
        "candidate_count": len(document.candidates),
        "excluded_observation_count": document.excluded_observation_count,
        "collection_mode": document.response_evidence.collection_mode,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _run_evaluate(args: argparse.Namespace) -> int:
    """Evaluate a verified local case without navigating, fetching, or modifying that case."""

    command = (
        f"python -m hawkeye evaluate {args.manifest} {args.case_directory} --report {args.report}"
    )
    try:
        result = evaluate_case(args.manifest, args.case_directory, args.report, command=command)
    except (EvaluationInputError, FileExistsError, ValueError) as error:
        print(json.dumps({"status": "rejected", "error": str(error)}, indent=2))
        return 2
    report = result.report
    print(
        json.dumps(
            {
                "status": "completed",
                "report_path": str(result.report_path),
                "evaluation_id": report.evaluation_id,
                "source_case_id": report.source_case_id,
                "passed": report.passed,
                "capture_outcome": report.source_case_capture_outcome,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.passed else 1


def _run_diagnose(args: argparse.Namespace) -> int:
    """Run a separate render diagnostic; it cannot replace canonical case evidence."""

    if args.allow_loopback_for_testing and os.environ.get("HAWKEYE_TEST_MODE") != "1":
        print(
            json.dumps(
                {
                    "status": "rejected",
                    "error": (
                        "--allow-loopback-for-testing requires HAWKEYE_TEST_MODE=1 and is only "
                        "intended for deterministic local fixtures"
                    ),
                },
                indent=2,
            )
        )
        return 2
    if args.mode == "fixture" and not args.allow_loopback_for_testing:
        print(
            json.dumps(
                {
                    "status": "rejected",
                    "error": "Fixture diagnostics require --allow-loopback-for-testing",
                },
                indent=2,
            )
        )
        return 2
    if args.mode == "live" and args.allow_loopback_for_testing:
        print(
            json.dumps(
                {
                    "status": "rejected",
                    "error": "Live diagnostics cannot use the loopback test safety policy",
                },
            )
        )
        return 2
    command = (
        f"python -m hawkeye diagnose {args.case_directory} --page-id {args.page_id} "
        f"--mode {args.mode}"
    )
    try:
        result = run_render_diagnostics(
            args.case_directory,
            page_id=args.page_id,
            mode=args.mode,
            timeout_seconds=args.timeout,
            safety_policy=SafetyPolicy(allow_loopback_for_testing=args.allow_loopback_for_testing),
            command=command,
        )
    except (DiagnosticInputError, FileExistsError, ValueError) as error:
        print(json.dumps({"status": "rejected", "error": str(error)}, indent=2))
        return 2
    document = result.document
    print(
        json.dumps(
            {
                "status": document.status,
                "diagnostics_path": str(result.path),
                "source_case_id": document.source_case_id,
                "source_page_id": document.source_page_id,
                "checkpoint_count": len(document.checkpoints),
                "total_diagnostic_time_ms": document.total_diagnostic_time_ms,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if document.status != "diagnostic_error" else 1


def _run_serve(args: argparse.Namespace) -> int:
    """Launch the V1 view with no externally reachable host option and no mutating endpoints."""

    try:
        run_local_server(args.cases, port=args.port, comparisons_root=args.comparisons)
    except (CaseIntegrityError, ValueError) as error:
        print(json.dumps({"status": "rejected", "error": str(error)}, indent=2))
        return 2
    return 0


def _run_demo(args: argparse.Namespace) -> int:
    """Build the offline judge walkthrough without network access or existing-file mutation."""

    try:
        result = build_demo(args.output)
    except (FileExistsError, ValueError) as error:
        print(json.dumps({"status": "rejected", "error": str(error)}, indent=2))
        return 2
    print(
        json.dumps(
            {
                "status": "completed",
                "output_directory": str(result.output_directory),
                "cases_directory": str(result.cases_directory),
                "comparisons_directory": str(result.comparisons_directory),
                "case_ids": result.case_ids,
                "comparison_path": str(result.comparison_path),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0
