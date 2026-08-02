"""Read-only evaluator for a completed, integrity-checked local case package."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from pydantic import ValidationError

from hawkeye import __version__
from hawkeye.evaluation.models import (
    EvaluationManifest,
    EvaluationReport,
    ExpectedInvariant,
    InvariantId,
    InvariantResult,
    InvariantValue,
)
from hawkeye.review_app.loader import CaseIntegrityError, CaseLoader, LoadedCase

type _ObservedValue = InvariantValue


class EvaluationInputError(ValueError):
    """Raised when a manifest, case package, or requested report destination is not valid."""


@dataclass(frozen=True)
class LoadedManifest:
    """A validated manifest with verified fixture-policy provenance."""

    manifest: EvaluationManifest
    path: Path
    sha256: str
    fixture_path: Path


@dataclass(frozen=True)
class EvaluationResult:
    """A report plus the new output path created by the read-only evaluation operation."""

    report: EvaluationReport
    report_path: Path


def load_manifest(manifest_path: Path | str) -> LoadedManifest:
    """Load a checked-in manifest and verify its referenced local policy fixture hash."""

    path = Path(manifest_path).expanduser()
    try:
        resolved_path = path.resolve(strict=True)
        raw_content = resolved_path.read_bytes()
        raw_payload = json.loads(raw_content)
        manifest = EvaluationManifest.model_validate(raw_payload)
    except (OSError, TypeError, ValueError, json.JSONDecodeError, ValidationError) as error:
        raise EvaluationInputError("Evaluation manifest cannot be validated") from error
    fixture_path = _resolve_fixture_manifest(resolved_path, manifest.fixture_manifest_path)
    fixture_sha256 = _sha256_file(fixture_path)
    if fixture_sha256 != manifest.fixture_manifest_sha256:
        raise EvaluationInputError("Evaluation fixture manifest SHA-256 does not match")
    return LoadedManifest(
        manifest=manifest,
        path=resolved_path,
        sha256=hashlib.sha256(raw_content).hexdigest(),
        fixture_path=fixture_path,
    )


def evaluate_case(
    manifest_path: Path | str,
    case_directory: Path | str,
    report_path: Path | str,
    *,
    command: str = "python -m hawkeye evaluate",
) -> EvaluationResult:
    """Assess a completed case without network access and write one new report atomically."""

    loaded_manifest = load_manifest(manifest_path)
    loaded_case = _load_case(case_directory)
    if _canonical_url(loaded_case.case.seed_url) != _canonical_url(
        loaded_manifest.manifest.input_url
    ):
        raise EvaluationInputError("Case seed URL does not match the evaluation manifest input URL")
    observed = _observed_invariants(loaded_case)
    results = [
        _evaluate_invariant(item, observed[item.id])
        for item in loaded_manifest.manifest.expected_invariants
    ]
    report = EvaluationReport(
        generated_at=datetime.now(UTC),
        engine_version=__version__,
        git_commit=_git_commit(),
        command=command,
        evaluation_id=loaded_manifest.manifest.evaluation_id,
        manifest_path=_repo_relative(loaded_manifest.path),
        manifest_sha256=loaded_manifest.sha256,
        fixture_manifest_path=loaded_manifest.manifest.fixture_manifest_path,
        fixture_manifest_sha256=loaded_manifest.manifest.fixture_manifest_sha256,
        input_url=loaded_manifest.manifest.input_url,
        source_case_id=loaded_case.case.case_id,
        source_case_manifest_sha256=loaded_case.manifest_sha256,
        source_case_capture_outcome=(
            loaded_case.case.capture_outcome.value
            if loaded_case.case.capture_outcome is not None
            else None
        ),
        source_case_content_usable=loaded_case.case.content_usable,
        artifact_sha256={
            evidence_id: record.sha256
            for evidence_id, record in sorted(loaded_case.evidence_by_id.items())
        },
        observed_invariants=results,
        passed=all(item.passed for item in results),
        environmental_restrictions=loaded_manifest.manifest.environmental_restrictions,
    )
    destination = _write_report(report_path, report)
    return EvaluationResult(report=report, report_path=destination)


def _load_case(case_directory: Path | str) -> LoadedCase:
    directory = Path(case_directory).expanduser()
    try:
        resolved = directory.resolve(strict=True)
        loader = CaseLoader(resolved.parent)
        return loader.load(resolved.name)
    except (OSError, CaseIntegrityError, KeyError, ValueError) as error:
        raise EvaluationInputError("Completed case package cannot be integrity-verified") from error


def _resolve_fixture_manifest(manifest_path: Path, declared_path: str) -> Path:
    declared = Path(declared_path.replace("\\", "/"))
    if declared.is_absolute() or ".." in declared.parts:
        raise EvaluationInputError("Evaluation fixture manifest path is not repository-relative")
    try:
        repository_root = manifest_path.parents[2]
    except IndexError as error:
        raise EvaluationInputError(
            "Evaluation manifest is outside the expected repository layout"
        ) from error
    candidate = repository_root / declared
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise EvaluationInputError("Evaluation fixture manifest is unavailable") from error
    if repository_root not in resolved.parents or not resolved.is_file():
        raise EvaluationInputError("Evaluation fixture manifest escapes the repository")
    return resolved


def _observed_invariants(loaded_case: LoadedCase) -> dict[InvariantId, _ObservedValue]:
    configuration = loaded_case.case.crawl_configuration
    completed_pages = [page for page in loaded_case.pages if page.state == "completed"]
    allowed_hosts = {host.casefold() for host in loaded_case.case.allowed_crawl_hosts}
    candidate_hosts = (
        {candidate.hostname.casefold() for candidate in loaded_case.candidates.candidates}
        if loaded_case.candidates is not None
        else set()
    )
    completed_hosts = {
        host
        for page in completed_pages
        if (host := _page_host(page.final_url or page.normalized_url)) is not None
    }
    return {
        "navigation_attempted": any(
            page.navigation_status != "pending" for page in loaded_case.pages
        ),
        "artifacts_preserved": True,
        "max_pages": configuration.max_pages_total
        if configuration is not None
        else len(loaded_case.pages),
        "max_depth": configuration.max_depth
        if configuration is not None
        else max((page.depth for page in loaded_case.pages), default=0),
        "external_documents_crawled": len(completed_hosts - allowed_hosts),
        "candidate_domains_crawled": len(completed_hosts & candidate_hosts),
        "review_status": "needs_review",
    }


def _evaluate_invariant(expected: ExpectedInvariant, observed: _ObservedValue) -> InvariantResult:
    if expected.operator == "equals":
        passed = observed == expected.value
    elif expected.operator == "less_or_equal":
        if (
            not isinstance(observed, int)
            or isinstance(observed, bool)
            or not isinstance(expected.value, int)
            or isinstance(expected.value, bool)
        ):
            raise EvaluationInputError("Numeric invariant received a non-numeric observation")
        passed = observed <= expected.value
    else:  # pragma: no cover - schema validation constrains the operator.
        raise EvaluationInputError("Evaluation invariant operator is unsupported")
    return InvariantResult(
        id=expected.id,
        operator=expected.operator,
        expected=expected.value,
        observed=observed,
        passed=passed,
    )


def _write_report(report_path: Path | str, report: EvaluationReport) -> Path:
    destination = Path(report_path).expanduser()
    if destination.exists():
        raise FileExistsError(f"Evaluation report already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True)
    try:
        with destination.open("x", encoding="utf-8") as output:
            output.write(f"{serialized}\n")
    except OSError as error:
        raise EvaluationInputError("Evaluation report cannot be written") from error
    return destination.resolve()


def _canonical_url(raw_url: str) -> str:
    parsed = urlsplit(raw_url)
    hostname = (parsed.hostname or "").casefold().rstrip(".")
    port = parsed.port
    default_port = 443 if parsed.scheme.casefold() == "https" else 80
    netloc = hostname if port in {None, default_port} else f"{hostname}:{port}"
    path = parsed.path or "/"
    return urlunsplit((parsed.scheme.casefold(), netloc, path, parsed.query, ""))


def _page_host(raw_url: str) -> str | None:
    try:
        hostname = urlsplit(raw_url).hostname
    except ValueError:
        return None
    return hostname.casefold() if hostname is not None else None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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


def _repo_relative(path: Path) -> str:
    repository_root = Path(__file__).resolve().parents[2]
    try:
        return path.relative_to(repository_root).as_posix()
    except ValueError:
        return str(path)
