"""Inventory and immutability checks for the optional live observation matrix."""

from __future__ import annotations

from pathlib import Path

import pytest

import hawkeye.smoke as smoke


def test_live_observation_inventory_contains_all_owner_supplied_targets() -> None:
    assert smoke.LIVE_OBSERVATION_URLS == (
        "https://888.com",
        "https://888casino.com",
        "https://888poker.com",
        "https://888sport.com",
        "https://betfair.com",
        "https://paddypower.com",
        "https://skybet.com",
        "https://skyvegas.com",
        "https://bet365.com",
        "https://williamhill.com",
        "https://qq101xfw.com",
        "https://qq888bet4cv.com",
    )


def test_live_observation_matrix_runs_each_target_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed: list[tuple[str, int]] = []

    def record(seed_url: str, _root: Path, _cases_root: Path, index: int) -> dict[str, object]:
        observed.append((seed_url, index))
        return {
            "input_domain": seed_url,
            "navigation_status": "failed",
            "capture_outcome": "navigation_error",
            "content_usable": False,
            "public_status": "collection_failed",
            "access_outcome": None,
            "capture_adequacy": "failed",
            "final_visible_text_chars": 0,
            "html_bytes": 0,
            "final_url": None,
            "duration_seconds": 0.0,
            "limitation_reasons": [],
            "failure_or_restriction_reason": "fixture",
        }

    monkeypatch.setattr(smoke, "_run_one", record)
    output = tmp_path / "observations"
    summary = smoke.run_live_smoke(output)
    assert len(observed) == 12
    assert observed == list(zip(smoke.LIVE_OBSERVATION_URLS, range(1, 13), strict=True))
    assert summary["limits"]["attempts_per_target"] == 1
    with pytest.raises(FileExistsError):
        smoke.run_live_smoke(output)
