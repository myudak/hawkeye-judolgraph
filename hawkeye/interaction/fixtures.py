"""Load and validate the authoritative ten controlled interaction scenarios."""

from __future__ import annotations

import json
from pathlib import Path

from .models import ControlledScenario


def load_controlled_scenarios(path: Path | str | None = None) -> list[ControlledScenario]:
    selected = (
        Path(path)
        if path is not None
        else Path(__file__).resolve().parents[2]
        / "evaluation"
        / "fixtures"
        / "controlled-interactions-v1.json"
    )
    payload = json.loads(selected.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("scenarios"), list):
        raise ValueError("Controlled interaction fixture must contain a scenarios list")
    scenarios = [ControlledScenario.model_validate(item) for item in payload["scenarios"]]
    if len(scenarios) != 10:
        raise ValueError("The controlled interaction benchmark must contain exactly 10 scenarios")
    if [item.ordinal for item in scenarios] != list(range(1, 11)):
        raise ValueError("Controlled interaction ordinals must be exactly 1 through 10")
    if len({item.scenario_id for item in scenarios}) != 10:
        raise ValueError("Controlled interaction scenario IDs must be unique")
    return scenarios
