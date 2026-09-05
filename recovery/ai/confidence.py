"""Calibrate fragment-classifier scores into forensic confidence labels."""

from __future__ import annotations

from typing import Any


HIGH = 0.80
MEDIUM = 0.50
DEFAULT_MIN = 0.70


def label_for(score: float) -> str:
    if score >= HIGH:
        return "high"
    if score >= MEDIUM:
        return "medium"
    return "low"


def should_keep(score: float, threshold: float = DEFAULT_MIN) -> bool:
    return score >= threshold


def session_summary(scores: list[float]) -> dict[str, Any]:
    if not scores:
        return {"count": 0, "mean": 0.0, "high": 0, "medium": 0, "low": 0, "flagged": 0}
    labels = [label_for(s) for s in scores]
    return {
        "count": len(scores),
        "mean": sum(scores) / len(scores),
        "high": labels.count("high"),
        "medium": labels.count("medium"),
        "low": labels.count("low"),
        "flagged": sum(1 for s in scores if not should_keep(s)),
    }
