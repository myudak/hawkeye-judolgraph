"""Deterministic, local-only candidate generation for Engine V0.2."""

from .generator import (
    CandidateGeneration,
    generate_candidates,
    generate_external_discovery_candidates,
)

__all__ = [
    "CandidateGeneration",
    "generate_candidates",
    "generate_external_discovery_candidates",
]
