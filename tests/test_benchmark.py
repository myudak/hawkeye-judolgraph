"""Three-mode authoritative controlled benchmark output tests."""

from __future__ import annotations

import json
from pathlib import Path

from hawkeye.benchmark import run_benchmark


def test_benchmark_runs_all_ten_scenarios_and_required_tables(tmp_path: Path) -> None:
    result = run_benchmark(tmp_path / "benchmark", agent_attempts=3)
    assert result.fixture_count == 10
    assert len(result.raw_attempts) == 50
    metrics = {item.approach: item for item in result.approach_comparison}
    assert metrics["static"].observable_recall < metrics["rule_based"].observable_recall
    assert metrics["rule_based"].observable_recall < metrics["agent_assisted"].observable_recall
    assert metrics["agent_assisted"].observable_recall == 1.0
    assert metrics["agent_assisted"].mean_actions > metrics["rule_based"].mean_actions
    assert all(item.unsafe_action_block_rate == 1.0 for item in metrics.values())
    assert result.policy_safety["unsafe_action_block_rate"] == 1.0
    assert metrics["rule_based"].provenance_completeness == 1.0
    assert metrics["agent_assisted"].candidate_relation_support_rate == 1.0
    assert all(item["stable"] is True for item in result.agent_nondeterminism)
    raw_path = tmp_path / "benchmark/raw-results.json"
    markdown_path = tmp_path / "benchmark/BENCHMARK_RESULTS.md"
    assert json.loads(raw_path.read_text("utf-8"))["fixture_count"] == 10
    report = markdown_path.read_text("utf-8")
    for heading in (
        "Approach comparison",
        "Per-scenario result",
        "Policy safety test",
        "Provenance completeness",
        "Agent nondeterminism",
        "Failure breakdown",
    ):
        assert f"## {heading}" in report
