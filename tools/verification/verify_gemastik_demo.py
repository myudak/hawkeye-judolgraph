"""Fail-closed, zero-network verifier for the frozen Gemastik G2 demonstration package.

This G3 wrapper intentionally leaves the HAWK-EYE runtime untouched. It creates a new sanitized
demo corpus in a caller-selected output directory, validates it through the existing verified
loader, evaluates fixture labels, and writes a report outside the immutable case directories.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from hawkeye.demo import DemoResult, build_demo  # noqa: E402
from hawkeye.review_app.loader import CaseLoader, case_details  # noqa: E402

BASELINE_COMMIT = "e55c1610c4e5a0a31891e3a69944aa1ffe2648ac"
BASELINE_TAG = "gemastik-g2"
PACKAGE_VERSION = "gemastik-g3-1"
BENCHMARK_PATH = REPOSITORY_ROOT / "evaluation" / "benchmarks" / "gemastik-g2-labels.json"
REPORT_NAME = "gemastik-g3-report.json"
SUMMARY_NAME = "SUMMARY.md"
Status = Literal["PASS", "FAIL", "NOT APPLICABLE", "OBSERVATIONAL ONLY"]
REQUIRED_LABEL_IDS = frozenset(
    {
        "demo-harbor-content",
        "demo-harbor-pending-candidate",
        "demo-harbor-noncanonical-diagnostic",
        "demo-restricted-capture",
        "demo-offline-comparison",
        "fixture-low-information-comparison",
        "fixture-invalid-provenance-warning",
    }
)
ALLOWED_LABEL_SOURCES = frozenset({"sanitized_demo", "existing_test_fixture"})


@dataclass(frozen=True)
class Check:
    """One human-readable verification result without machine-specific output paths."""

    id: str
    status: Status
    detail: str


class VerificationError(ValueError):
    """Raised when a package input cannot support a truthful G3 verification claim."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify the frozen gemastik-g2 demo package without network access"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New report directory; the verifier refuses an existing directory",
    )
    parser.add_argument(
        "--skip-quality",
        action="store_true",
        help="Skip pytest/ruff/mypy only for narrow local diagnostics; not the judge command",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = args.output.expanduser().resolve()
    if output.exists():
        _print_terminal_error(f"Refusing to overwrite existing verification output: {output.name}")
        return 2
    output_error = _unsafe_output_error(output)
    if output_error is not None:
        _print_terminal_error(output_error)
        return 2
    output.mkdir(parents=True)
    checks: list[Check] = []
    benchmark_hash: str | None = None
    demo_manifest_hash: str | None = None
    try:
        benchmark, benchmark_hash = _load_benchmark_manifest()
        checks.append(
            Check(
                "benchmark-label-contract",
                "PASS",
                "Fixture-only labels cover usable, restricted, pending, diagnostic, comparison, "
                "and provenance states.",
            )
        )
        checks.extend(_verify_baseline(benchmark))
        demo = _build_demo_without_network(output / "sanitized-demo")
        demo_manifest_hash = _demo_manifest_hash(demo.cases_directory)
        checks.extend(_verify_demo_and_labels(demo, benchmark, demo_manifest_hash))
        checks.extend(_verify_documentation(benchmark))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        checks.append(Check("package-inputs", "FAIL", _safe_error(error)))

    if args.skip_quality:
        checks.append(
            Check(
                "quality-suite",
                "NOT APPLICABLE",
                "Skipped only because --skip-quality was explicitly supplied.",
            )
        )
    else:
        checks.extend(_run_quality_suite())

    passed = all(check.status != "FAIL" for check in checks)
    report = {
        "schema_version": "1.0",
        "evaluation_package_version": PACKAGE_VERSION,
        "target": {"commit": BASELINE_COMMIT, "tag": BASELINE_TAG},
        "generated_at": datetime.now(UTC).isoformat(),
        "verification_command": (
            "python tools/verification/verify_gemastik_demo.py --output <new-output-directory>"
        ),
        "sanitized_demo_manifest_sha256": demo_manifest_hash,
        "benchmark_label_manifest_sha256": benchmark_hash,
        "quality_suite_skipped": args.skip_quality,
        "verification_complete": passed and not args.skip_quality,
        "passed": passed,
        "checks": [asdict(check) for check in checks],
    }
    _write_report(output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if passed else 1


def _print_terminal_error(message: str) -> None:
    print(json.dumps({"status": "rejected", "error": message}, indent=2, sort_keys=True))


def _unsafe_output_error(output: Path) -> str | None:
    """Keep generated reports outside frozen code and checked-in package inputs."""

    runtime_root = REPOSITORY_ROOT / "hawkeye"
    if _is_within(output, runtime_root):
        return "Verification output may not be created inside the frozen hawkeye runtime."
    if _is_within(output, REPOSITORY_ROOT):
        allowed_roots = (
            REPOSITORY_ROOT / "verification-output",
            REPOSITORY_ROOT / "evaluation" / "reports",
        )
        if not any(_is_within(output, allowed) for allowed in allowed_roots):
            return (
                "Repository-local verification output must be under verification-output or "
                "evaluation/reports."
            )
    return None


def _is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


def _load_benchmark_manifest() -> tuple[dict[str, Any], str]:
    try:
        payload = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    except OSError as error:
        raise VerificationError("Benchmark-label manifest cannot be read") from error
    if not isinstance(payload, dict):
        raise VerificationError("Benchmark-label manifest must be a JSON object")
    if payload.get("schema_version") != "1.0" or payload.get("label_version") != "1.0":
        raise VerificationError(
            "Benchmark-label manifest has an unsupported schema or label version"
        )
    if payload.get("evaluation_package_version") != PACKAGE_VERSION:
        raise VerificationError("Benchmark-label manifest has the wrong evaluation-package version")
    target = payload.get("target")
    if not isinstance(target, dict) or target.get("commit") != BASELINE_COMMIT:
        raise VerificationError("Benchmark-label manifest targets the wrong baseline commit")
    if target.get("tag") != BASELINE_TAG:
        raise VerificationError("Benchmark-label manifest targets the wrong baseline tag")
    labels = payload.get("labels")
    if not isinstance(labels, list) or not labels:
        raise VerificationError("Benchmark-label manifest must contain fixture-backed labels")
    _validate_benchmark_labels(payload, labels)
    return payload, _canonical_sha256(payload)


def _validate_benchmark_labels(payload: dict[str, Any], labels: list[Any]) -> None:
    """Require the complete, fixture-only evaluation contract before generating a report."""

    sanitized_demo = payload.get("sanitized_demo")
    if not isinstance(sanitized_demo, dict):
        raise VerificationError("Benchmark-label manifest has no sanitized-demo definition")
    expected_hash = sanitized_demo.get("fixture_manifest_sha256")
    case_ids = sanitized_demo.get("case_ids")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise VerificationError("Sanitized-demo manifest hash is absent or malformed")
    if not isinstance(case_ids, list) or not all(isinstance(case_id, str) for case_id in case_ids):
        raise VerificationError("Sanitized-demo case IDs are absent or malformed")

    identifiers: set[str] = set()
    for label in labels:
        if not isinstance(label, dict):
            raise VerificationError("A benchmark label must be a JSON object")
        identifier = label.get("benchmark_case_id")
        source = label.get("source")
        if not isinstance(identifier, str) or not identifier:
            raise VerificationError("A benchmark label has no usable identifier")
        if identifier in identifiers:
            raise VerificationError("Benchmark-label identifiers must be unique")
        identifiers.add(identifier)
        if source not in ALLOWED_LABEL_SOURCES:
            raise VerificationError("Benchmark labels must use a fixture-only source")
        if not isinstance(label.get("expected_properties"), dict):
            raise VerificationError("A benchmark label has no expected properties")
        if not isinstance(label.get("expected_invariants"), list):
            raise VerificationError("A benchmark label has no expected invariants")
        if not isinstance(label.get("prohibited_interpretations"), list):
            raise VerificationError("A benchmark label has no prohibited interpretations")
        if source == "sanitized_demo" and label.get("case_id") not in case_ids:
            raise VerificationError("A sanitized-demo label names an unknown fixture case")
        if source == "existing_test_fixture" and not isinstance(label.get("test_nodeid"), str):
            raise VerificationError("An existing-fixture label has no pytest node ID")

    missing = REQUIRED_LABEL_IDS - identifiers
    if missing:
        raise VerificationError(
            f"Benchmark labels omit required observable states: {', '.join(sorted(missing))}"
        )


def _verify_baseline(benchmark: dict[str, Any]) -> list[Check]:
    checks: list[Check] = []
    tag_commit = _git_output(["rev-parse", f"{BASELINE_TAG}^{{commit}}"])
    if tag_commit == BASELINE_COMMIT:
        checks.append(
            Check("baseline-tag", "PASS", f"{BASELINE_TAG} resolves to the frozen G2 commit.")
        )
    else:
        checks.append(
            Check("baseline-tag", "FAIL", "The required gemastik-g2 tag is absent or mismatched.")
        )

    manifest_target = benchmark["target"]
    if manifest_target["commit"] == BASELINE_COMMIT and manifest_target["tag"] == BASELINE_TAG:
        checks.append(
            Check("baseline-label-target", "PASS", "Benchmark labels name the frozen G2 baseline.")
        )
    else:
        checks.append(
            Check(
                "baseline-label-target",
                "FAIL",
                "Benchmark labels do not name the frozen G2 baseline.",
            )
        )

    core_diff = _git_returncode(["diff", "--quiet", BASELINE_COMMIT, "--", "hawkeye"])
    untracked = _git_output(["ls-files", "--others", "--exclude-standard", "--", "hawkeye"])
    if core_diff == 0 and not untracked:
        checks.append(
            Check(
                "baseline-core-tree",
                "PASS",
                "The runtime package matches gemastik-g2; G3 changes are wrapper artifacts only.",
            )
        )
    else:
        checks.append(
            Check(
                "baseline-core-tree",
                "FAIL",
                "The HAWK-EYE runtime differs from the frozen gemastik-g2 baseline.",
            )
        )
    return checks


def _build_demo_without_network(output: Path) -> DemoResult:
    with _network_denied():
        return build_demo(output)


@contextmanager
def _network_denied() -> Iterator[None]:
    """Deny normal DNS and socket-connection primitives while building and reading demo fixtures."""

    original_getaddrinfo = socket.getaddrinfo
    original_create_connection = socket.create_connection

    def denied(*_args: object, **_kwargs: object) -> object:
        raise AssertionError(
            "G3 offline verification must not use network resolution or connections"
        )

    socket.getaddrinfo = denied  # type: ignore[assignment]
    socket.create_connection = denied  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.getaddrinfo = original_getaddrinfo
        socket.create_connection = original_create_connection


def _demo_manifest_hash(cases_directory: Path) -> str:
    records: list[dict[str, str]] = []
    for path in sorted(cases_directory.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_dir():
            continue
        if path.is_symlink() or not path.is_file():
            raise VerificationError("Sanitized demo contains a non-regular artifact")
        records.append(
            {
                "path": path.relative_to(cases_directory).as_posix(),
                "sha256": _sha256_bytes(path.read_bytes()),
            }
        )
    if not records:
        raise VerificationError("Sanitized demo has no case artifacts")
    return _canonical_sha256({"case_artifacts": records})


def _verify_demo_and_labels(
    demo: DemoResult, benchmark: dict[str, Any], demo_manifest_hash: str
) -> list[Check]:
    checks: list[Check] = []
    expected_demo = benchmark.get("sanitized_demo")
    if not isinstance(expected_demo, dict):
        raise VerificationError("Benchmark-label manifest has no sanitized-demo definition")
    expected_hash = expected_demo.get("fixture_manifest_sha256")
    if expected_hash == demo_manifest_hash:
        checks.append(
            Check("sanitized-demo-manifest", "PASS", "Generated fixture hashes match G2 labels.")
        )
    else:
        checks.append(
            Check(
                "sanitized-demo-manifest",
                "FAIL",
                "Generated sanitized-demo artifacts differ from the frozen label manifest.",
            )
        )

    expected_case_ids = expected_demo.get("case_ids")
    if expected_case_ids == demo.case_ids:
        checks.append(
            Check("sanitized-demo-cases", "PASS", "Expected fixture case IDs were generated.")
        )
    else:
        checks.append(
            Check("sanitized-demo-cases", "FAIL", "Generated fixture case IDs differ from labels.")
        )

    with _network_denied():
        loader = CaseLoader(demo.cases_directory, comparisons_root=demo.comparisons_directory)
        summaries = loader.list_cases()
        details_by_case: dict[str, dict[str, Any]] = {}
        comparisons_by_case: dict[str, list[dict[str, Any]]] = {}
        for case_id in demo.case_ids:
            loaded = loader.load(case_id)
            comparisons, warning = loader.comparisons_for_case(loaded)
            detail = case_details(
                loaded,
                comparisons=comparisons,
                comparison_integrity_warning=warning,
            )
            details_by_case[case_id] = detail
            comparisons_by_case[case_id] = detail["comparisons"]

    if all(summary.get("integrity") == "verified" for summary in summaries):
        checks.append(
            Check(
                "case-integrity", "PASS", "All sanitized case packages passed the verified loader."
            )
        )
    else:
        checks.append(
            Check("case-integrity", "FAIL", "At least one sanitized case package failed integrity.")
        )

    for label in benchmark["labels"]:
        checks.append(_verify_label(label, details_by_case, comparisons_by_case))
    return checks


def _verify_label(
    label: Any,
    details_by_case: dict[str, dict[str, Any]],
    comparisons_by_case: dict[str, list[dict[str, Any]]],
) -> Check:
    if not isinstance(label, dict) or not isinstance(label.get("benchmark_case_id"), str):
        return Check("benchmark-label", "FAIL", "A benchmark label has no usable identifier.")
    identifier = label["benchmark_case_id"]
    source = label.get("source")
    if source == "existing_test_fixture":
        return _verify_existing_fixture_label(identifier, label)
    if source != "sanitized_demo":
        return Check(identifier, "FAIL", "Benchmark label has an unsupported fixture source.")
    case_id = label.get("case_id")
    detail = details_by_case.get(case_id)
    if detail is None:
        return Check(
            identifier, "FAIL", "Benchmark label references an absent sanitized demo case."
        )
    properties = label.get("expected_properties")
    if not isinstance(properties, dict):
        return Check(identifier, "FAIL", "Benchmark label has no expected properties.")

    actual: dict[str, Any] = {
        "capture_outcome": detail.get("capture_outcome"),
        "content_usable": detail.get("content_usable"),
        "candidate_count": len(detail.get("candidates", [])),
        "entity_count": len(detail.get("entities", [])),
        "candidate_status": detail["candidates"][0]["status"] if detail.get("candidates") else None,
        "relationship": detail["candidates"][0]["relationship"]
        if detail.get("candidates")
        else None,
        "diagnostic_status": detail["diagnostic"]["status"] if detail.get("diagnostic") else None,
    }
    comparison_with = label.get("comparison_with")
    if isinstance(comparison_with, str):
        comparison = next(
            (
                document
                for document in comparisons_by_case.get(case_id, [])
                if comparison_with in {document["left_case_id"], document["right_case_id"]}
            ),
            None,
        )
        if comparison is None:
            return Check(
                identifier, "FAIL", "Benchmark label requires a missing comparison document."
            )
        actual["comparison_review_status"] = comparison["review_status"]
        component_name = properties.get("comparison_component_name")
        if isinstance(component_name, str):
            component = next(
                (item for item in comparison["components"] if item["name"] == component_name),
                None,
            )
            if component is None:
                return Check(
                    identifier, "FAIL", "Benchmark label requires a missing comparison component."
                )
            actual["comparison_component_name"] = component["name"]
            actual["comparison_component_status"] = component["status"]
            actual["comparison_component_available"] = component["available"]

    mismatches = [name for name, expected in properties.items() if actual.get(name) != expected]
    if mismatches:
        return Check(identifier, "FAIL", f"Label mismatch: {', '.join(sorted(mismatches))}.")
    return Check(
        identifier, "PASS", "Fixture properties and non-conclusive semantics match labels."
    )


def _verify_existing_fixture_label(identifier: str, label: dict[str, Any]) -> Check:
    nodeid = label.get("test_nodeid")
    if not isinstance(nodeid, str) or "::" not in nodeid:
        return Check(identifier, "FAIL", "Existing-fixture label has no valid pytest node ID.")
    relative_path, test_name = nodeid.split("::", maxsplit=1)
    path = REPOSITORY_ROOT / relative_path
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return Check(identifier, "FAIL", "Existing-fixture label points to a missing test file.")
    if f"def {test_name}" not in text:
        return Check(
            identifier, "FAIL", "Existing-fixture label points to a missing test function."
        )
    return Check(
        identifier, "PASS", "Fixture-backed semantics are covered by the named automated test."
    )


def _verify_documentation(benchmark: dict[str, Any]) -> list[Check]:
    required_paths = [
        REPOSITORY_ROOT / "docs" / "evaluator" / "README.md",
        REPOSITORY_ROOT / "docs" / "evaluator" / "JUDGE-GUIDE.md",
        REPOSITORY_ROOT / "docs" / "evaluator" / "JUDGING-CHECKLIST.md",
        REPOSITORY_ROOT / "docs" / "THREAT-MODEL.md",
        REPOSITORY_ROOT / "docs" / "PRESENTATION-STORYBOARD.md",
        REPOSITORY_ROOT / "docs" / "DEMO.md",
    ]
    missing = [
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for path in required_paths
        if not path.is_file()
    ]
    if missing:
        return [
            Check(
                "evaluator-documentation", "FAIL", f"Missing required docs: {', '.join(missing)}."
            )
        ]

    documentation = "\n".join(path.read_text(encoding="utf-8") for path in required_paths)
    required_terms = [
        BASELINE_COMMIT,
        BASELINE_TAG,
        "Pending lead",
        "Relationship: not determined",
        "Evidence-similarity score",
        "Review status: needs review",
        "python tools/verification/verify_gemastik_demo.py --output",
        "127.0.0.1",
        "/api/cases",
        "v0.3-offline-comparison-1",
    ]
    missing_terms = [term for term in required_terms if term not in documentation]
    checks = [
        Check(
            "evaluator-documentation",
            "PASS" if not missing_terms else "FAIL",
            "Required files and implemented terminology are present."
            if not missing_terms
            else f"Documentation drift: {', '.join(missing_terms)}.",
        )
    ]
    threat_model = (REPOSITORY_ROOT / "docs" / "THREAT-MODEL.md").read_text(encoding="utf-8")
    if "```mermaid" in threat_model and "DNS TOCTOU" in threat_model:
        checks.append(
            Check(
                "threat-model",
                "PASS",
                "Threat model includes the implemented diagram and residual DNS risk.",
            )
        )
    else:
        checks.append(
            Check(
                "threat-model",
                "FAIL",
                "Threat model lacks the required diagram or DNS residual-risk wording.",
            )
        )
    return checks


def _run_quality_suite() -> list[Check]:
    commands = [
        ("pytest", [sys.executable, "-m", "pytest", "-q"]),
        ("ruff-format", ["ruff", "format", "--check", "."]),
        ("ruff-check", ["ruff", "check", "."]),
        ("mypy", ["mypy", "hawkeye"]),
        ("git-diff-check", ["git", "diff", "--check"]),
    ]
    checks: list[Check] = []
    for name, command in commands:
        try:
            completed = subprocess.run(
                command,
                cwd=REPOSITORY_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as error:
            checks.append(
                Check(name, "FAIL", f"Could not start local command: {_safe_error(error)}")
            )
            continue
        if completed.returncode == 0:
            checks.append(Check(name, "PASS", "Completed successfully."))
        else:
            checks.append(Check(name, "FAIL", f"Exited with status {completed.returncode}."))
    return checks


def _git_output(arguments: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    return completed.stdout.strip() if completed.returncode == 0 else None


def _git_returncode(arguments: list[str]) -> int:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
        ).returncode
    except OSError:
        return 127


def _write_report(output: Path, report: dict[str, Any]) -> None:
    (output / REPORT_NAME).write_text(
        f"{json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)}\n", encoding="utf-8"
    )
    lines = [
        "# Gemastik G3 verification summary",
        "",
        f"- Target: `{BASELINE_TAG}` / `{BASELINE_COMMIT}`",
        f"- Package version: `{PACKAGE_VERSION}`",
        f"- Result: `{'PASS' if report['passed'] else 'FAIL'}`",
        f"- Complete judge-quality run: `{'yes' if report['verification_complete'] else 'no'}`",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in report["checks"]:
        detail = str(check["detail"]).replace("|", "\\|")
        lines.append(f"| {check['id']} | {check['status']} | {detail} |")
    lines.append("")
    (output / SUMMARY_NAME).write_text("\n".join(lines), encoding="utf-8")


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _canonical_sha256(value: object) -> str:
    serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return _sha256_bytes(serialized.encode("utf-8"))


def _safe_error(error: BaseException) -> str:
    return str(error).replace(str(REPOSITORY_ROOT), "<repository>")[:300]


if __name__ == "__main__":
    raise SystemExit(main())
