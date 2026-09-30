from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "apps/web/src/demo"


def test_demo_artifacts_and_observations_retain_synthetic_provenance() -> None:
    package = json.loads((ROOT / "fixtures.json").read_text(encoding="utf-8"))
    assert len(package["runs"]) == 3
    for run in package["runs"]:
        assert run["source_kind"] == "synthetic_fixture"
        assert run["seed_url"].endswith(".demo.invalid/")
        case = run["source_case"]
        evidence = {item["id"]: item for item in case["evidence"]}
        for record in evidence.values():
            artifact = ROOT / "assets" / package["assets"][case["case_id"]][record["id"]]
            assert artifact.is_file()
            assert hashlib.sha256(artifact.read_bytes()).hexdigest() == record["sha256"]
        for observation in case["observations"]:
            assert observation["source_artifact_id"] in evidence
            assert observation["screenshot_evidence_id"] in evidence
            source = package["assets"][case["case_id"]][observation["source_artifact_id"]]
            assert observation["display_value"] in (ROOT / "assets" / source).read_text()
            assert package["limitation"] in observation["limitations"]
        nodes = {item["id"] for item in run["graph"]["nodes"]}
        assert len(nodes) == len(run["graph"]["nodes"])
        events = {item["event_id"] for item in run["events"]}
        for edge in run["graph"]["edges"]:
            assert edge["source"] in nodes and edge["target"] in nodes
            assert set(edge["supporting_event_ids"]).issubset(events)
        assert all("screenshot" not in item["kind"] for item in run["graph"]["nodes"])
        if case["capture_adequacy"] == "limited":
            assert not case["observations"]
            assert not case["candidates"]
            assert case["gambling_indicator_count"] == 0
