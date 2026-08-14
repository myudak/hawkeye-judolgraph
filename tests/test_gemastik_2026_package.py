"""Truthfulness and structure checks for the G9 Markdown source package."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "competition" / "gemastik-2026"
MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def test_required_markdown_package_and_asset_directories_exist() -> None:
    required = {
        "README.md",
        "proposal/PROPOSAL.md",
        "proposal/RESEARCH_AND_CITATIONS.md",
        "technical/TECHNICAL_DOCUMENT.md",
        "technical/IMPLEMENTATION_STATUS.md",
        "technical/CLAIM_EVIDENCE_MATRIX.md",
        "technical/LIBRARIES_AND_LICENSES.md",
        "technical/BENCHMARK_RESULTS.md",
        "submission/VIDEO_SCRIPT_3_MINUTES.md",
        "submission/SUBMISSION_CHECKLIST.md",
        "submission/ORIGINALITY_STATEMENT_DRAFT.md",
        "submission/FIGURE_INDEX.md",
    }
    assert all((PACKAGE / path).is_file() for path in required)
    for path in ("technical/README.md", "video/README.md"):
        assert (PACKAGE / "assets" / path).is_file()

    screenshot_root = PACKAGE / "assets" / "technical-current"
    manifest_path = screenshot_root / "screenshot-manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(manifest["screenshots"]) == 6
    for screenshot in manifest["screenshots"]:
        screenshot_path = screenshot_root / screenshot["file"]
        assert screenshot_path.is_file()
        assert screenshot_path.stat().st_size == screenshot["bytes"]
        assert hashlib.sha256(screenshot_path.read_bytes()).hexdigest() == screenshot["sha256"]

    # Reference PDFs may live under assets/source material, but the preliminary package must not
    # claim a generated submission PDF before the human-owned export gate is complete.
    assert not list((PACKAGE / "deliverables").glob("*.pdf"))


def test_local_markdown_image_references_resolve() -> None:
    for markdown in PACKAGE.rglob("*.md"):
        for reference in MARKDOWN_IMAGE.findall(markdown.read_text(encoding="utf-8")):
            assert "://" not in reference
            assert (markdown.parent / reference).resolve().is_file(), (
                f"Broken image reference in {markdown.relative_to(PACKAGE)}: {reference}"
            )


def test_proposal_uses_official_section_order_and_public_name_placeholder() -> None:
    proposal = (PACKAGE / "proposal" / "PROPOSAL.md").read_text(encoding="utf-8")
    headings = [line for line in proposal.splitlines() if line.startswith("## ")]
    assert headings == [
        "## 1. Judul/Nama Perangkat Lunak",
        "## 2. Latar Belakang Ide Perangkat Lunak",
        "## 3. Tujuan dan Manfaat Dikembangkannya Perangkat Lunak",
        "## 4. Batasan Perangkat Lunak yang Dikembangkan",
        "## 5. Metodologi Pengembangan Perangkat Lunak",
        "## 6. Analisis Kebutuhan dan Desain Solusi Perangkat Lunak",
        "## 7. Implementasi Perangkat Lunak",
        "## 8. Screenshot Mockup Interface Perangkat Lunak",
        "## 9. Dokumentasi Cara Penggunaan Perangkat Lunak",
    ]
    assert proposal.startswith("# [NAMA PRODUK FINAL]")
    assert "Target rendered-page plan" in proposal
    assert "not a verified page count" in proposal


def test_benchmark_claims_match_checked_in_raw_results() -> None:
    raw = json.loads(
        (ROOT / "evaluation/benchmarks/g4-g9-controlled-results/raw-results.json").read_text(
            encoding="utf-8"
        )
    )
    claims = (PACKAGE / "technical" / "BENCHMARK_RESULTS.md").read_text(encoding="utf-8")
    assert raw["fixture_count"] == 10
    assert raw["policy_safety"]["unsafe_action_block_rate"] == 1.0
    for row in raw["approach_comparison"]:
        assert f"{row['observable_recall']:.4f}" in claims
        assert f"{row['task_success_rate']:.4f}" in claims
        assert f"{row['provenance_completeness']:.4f}" in claims


def test_status_table_uses_only_allowed_statuses_and_todos_are_explicit() -> None:
    status = (PACKAGE / "technical" / "IMPLEMENTATION_STATUS.md").read_text(encoding="utf-8")
    allowed = {"implemented", "partially implemented", "planned", "deferred"}
    rows = [line for line in status.splitlines() if line.startswith("|")][2:]
    for row in rows:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        assert cells[1] in allowed
    combined = "\n".join(path.read_text(encoding="utf-8") for path in PACKAGE.rglob("*.md"))
    assert "TODO — requires human confirmation" in combined
    assert "TODO — requires external source" in combined
    assert "TODO — requires completed test" in combined
