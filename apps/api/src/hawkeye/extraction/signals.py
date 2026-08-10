"""Internal deterministic extraction representation before IDs are assigned."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExtractedSignal:
    """A normalized candidate signal with a stable priority for duplicate collapse."""

    type: str
    value: str
    normalized_value: str
    extraction_method: str
    confidence: float = 1.0
    details: dict[str, str] = field(default_factory=dict)
    priority: int = 0
