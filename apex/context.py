"""Context Fabric: correlation/divergence/SMT/MTF with conflict 0.4 and redundancy 0.25 penalties."""

from __future__ import annotations

CONFLICT_PENALTY = 0.4
REDUNDANCY_PENALTY = 0.25


def aggregate_context(directions: list[str], strengths: list[float]) -> dict:
    if not directions:
        return {"score": 0.0, "quality": "UNAVAILABLE"}
    unique = set(directions) - {"FLAT"}
    score = sum(strengths) / max(len(strengths), 1)
    if len(unique) > 1:
        score *= 1.0 - CONFLICT_PENALTY
    if len(directions) > len(set(directions)):
        score *= 1.0 - REDUNDANCY_PENALTY
    return {"score": score, "quality": "VALID", "conflict": len(unique) > 1}
