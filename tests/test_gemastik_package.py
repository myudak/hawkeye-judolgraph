"""G3 evaluator-package checks without invoking the verifier's recursive quality-suite mode."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPOSITORY_ROOT = Path(__file__).parents[1]
VERIFIER_PATH = REPOSITORY_ROOT / "tools" / "verification" / "verify_gemastik_demo.py"


def _load_verifier() -> ModuleType:
    specification = importlib.util.spec_from_file_location("gemastik_verifier", VERIFIER_PATH)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def test_g3_verifier_detects_the_intentional_post_g3_runtime_evolution(tmp_path: Path) -> None:
    verifier = _load_verifier()
    output = tmp_path / "g3-report"

    exit_code = verifier.main(["--output", str(output), "--skip-quality"])

    assert exit_code == 1
    report = json.loads((output / "gemastik-g3-report.json").read_text(encoding="utf-8"))
    assert report["target"] == {
        "commit": "e55c1610c4e5a0a31891e3a69944aa1ffe2648ac",
        "tag": "gemastik-g2",
    }
    assert len(report["sanitized_demo_manifest_sha256"]) == 64
    assert len(report["benchmark_label_manifest_sha256"]) == 64
    assert report["passed"] is False
    assert report["verification_complete"] is False
    checks = {check["id"]: check for check in report["checks"]}
    assert checks["benchmark-label-contract"]["status"] == "PASS"
    assert checks["baseline-core-tree"]["status"] == "FAIL"
    assert checks["sanitized-demo-manifest"]["status"] == "FAIL"
    assert checks["case-integrity"]["status"] == "PASS"
    assert checks["quality-suite"]["status"] == "NOT APPLICABLE"
    assert "Target:" in (output / "SUMMARY.md").read_text(encoding="utf-8")


def test_g3_verifier_fails_visibly_when_baseline_identity_is_wrong(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    verifier = _load_verifier()

    def missing_tag(arguments: list[str]) -> str | None:
        return None if arguments[:1] == ["rev-parse"] else ""

    monkeypatch.setattr(verifier, "_git_output", missing_tag)
    output = tmp_path / "g3-failed-report"

    exit_code = verifier.main(["--output", str(output), "--skip-quality"])

    assert exit_code == 1
    report = json.loads((output / "gemastik-g3-report.json").read_text(encoding="utf-8"))
    checks = {check["id"]: check for check in report["checks"]}
    assert checks["baseline-tag"]["status"] == "FAIL"
    assert report["passed"] is False


def test_g3_label_contract_rejects_a_missing_required_observable_state() -> None:
    verifier = _load_verifier()
    benchmark = json.loads(
        (REPOSITORY_ROOT / "evaluation" / "benchmarks" / "gemastik-g2-labels.json").read_text(
            encoding="utf-8"
        )
    )
    labels = [
        label
        for label in benchmark["labels"]
        if label["benchmark_case_id"] != "demo-harbor-pending-candidate"
    ]

    with pytest.raises(verifier.VerificationError, match="omit required observable states"):
        verifier._validate_benchmark_labels(benchmark, labels)


def test_g3_verifier_rejects_reports_inside_the_frozen_runtime() -> None:
    verifier = _load_verifier()

    error = verifier._unsafe_output_error(REPOSITORY_ROOT / "hawkeye" / "g3-report")

    assert error is not None
    assert "frozen hawkeye runtime" in error


def test_g3_docs_are_portable_and_the_frozen_tags_stay_immutable() -> None:
    documents = [
        REPOSITORY_ROOT / "docs" / "evaluator" / "README.md",
        REPOSITORY_ROOT / "docs" / "evaluator" / "JUDGE-GUIDE.md",
        REPOSITORY_ROOT / "docs" / "evaluator" / "JUDGING-CHECKLIST.md",
        REPOSITORY_ROOT / "docs" / "security" / "THREAT-MODEL.md",
        REPOSITORY_ROOT / "docs" / "guides" / "PRESENTATION-STORYBOARD.md",
    ]
    joined = "\n".join(document.read_text(encoding="utf-8") for document in documents)

    assert "C:\\" not in joined
    assert "/Users/" not in joined
    assert "Pending lead" in joined
    assert "Relationship: not determined" in joined
    assert "Evidence-similarity score" in joined
    assert "Review status: needs review" in joined
    assert "```mermaid" in joined
    g2 = subprocess.run(
        ["git", "rev-parse", "gemastik-g2^{}"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    g3 = subprocess.run(
        ["git", "rev-parse", "gemastik-g3^{}"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert g2.stdout.strip() == "e55c1610c4e5a0a31891e3a69944aa1ffe2648ac"
    assert g3.stdout.strip() == "ee59a41e5ac638ec72ddf9706653e75fee7d7138"
    assert not re.search(r"(?:^|\s)[A-Za-z]:[\\/]", joined)
