"""Truthfulness and structure checks for the G9 Markdown source package."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "gemastik-2026"


def test_required_markdown_package_and_asset_directories_exist() -> None:
    required = {
        "README.md",
        "PROPOSAL.md",
        "TECHNICAL_DOCUMENT.md",
        "VIDEO_SCRIPT_3_MINUTES.md",
        "SUBMISSION_CHECKLIST.md",
        "IMPLEMENTATION_STATUS.md",
        "CLAIM_EVIDENCE_MATRIX.md",
        "LIBRARIES_AND_LICENSES.md",
        "ORIGINALITY_STATEMENT_DRAFT.md",
        "RESEARCH_AND_CITATIONS.md",
        "FIGURE_INDEX.md",
        "BENCHMARK_RESULTS.md",
    }
    assert {path.name for path in PACKAGE.glob("*.md")} == required
    for name in ("proposal", "technical", "video"):
        assert (PACKAGE / "assets" / name / "README.md").is_file()
    assert not list(PACKAGE.rglob("*.pdf"))


def test_proposal_uses_official_section_order_and_public_name_placeholder() -> None:
    proposal = (PACKAGE / "PROPOSAL.md").read_text(encoding="utf-8")
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
    claims = (PACKAGE / "BENCHMARK_RESULTS.md").read_text(encoding="utf-8")
    assert raw["fixture_count"] == 10
    assert raw["policy_safety"]["unsafe_action_block_rate"] == 1.0
    for row in raw["approach_comparison"]:
        assert f"{row['observable_recall']:.4f}" in claims
        assert f"{row['task_success_rate']:.4f}" in claims
        assert f"{row['provenance_completeness']:.4f}" in claims


def test_status_table_uses_only_allowed_statuses_and_todos_are_explicit() -> None:
    status = (PACKAGE / "IMPLEMENTATION_STATUS.md").read_text(encoding="utf-8")
    allowed = {"implemented", "partially implemented", "planned", "deferred"}
    rows = [line for line in status.splitlines() if line.startswith("|")][2:]
    for row in rows:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        assert cells[1] in allowed
    combined = "\n".join(path.read_text(encoding="utf-8") for path in PACKAGE.glob("*.md"))
    assert "TODO — requires human confirmation" in combined
    assert "TODO — requires external source" in combined
    assert "TODO — requires completed test" in combined
