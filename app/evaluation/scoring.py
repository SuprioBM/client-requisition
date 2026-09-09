"""Deterministic lead scoring.

The LLM proposes sub-scores; this module clamps them to their ranges and computes
the total. Score arithmetic is never delegated to the model.
"""

from __future__ import annotations

from app.evaluation.prompts import SCORING_VERSION
from app.schemas.evaluation import LeadScoreInput

_RANGES = {
    "problem_severity": 25,
    "business_value": 25,
    "evidence_confidence": 20,
    "solution_fit": 20,
    "contactability": 10,
}


def _evidence_ceiling(evidence: list[dict]) -> int:
    """Deterministic ceiling on evidence_confidence based on evidence quantity/quality."""
    if not evidence:
        return 4
    strong = [e for e in evidence if float(e.get("confidence", 0)) >= 0.7]
    mean = sum(float(e.get("confidence", 0)) for e in evidence) / len(evidence)
    if len(evidence) < 3 or not strong:
        return 8
    if len(evidence) < 6 or mean < 0.55:
        return 14
    return 20


def compute_score(
    raw: LeadScoreInput, *, has_evidence: bool | None = None, is_opportunity: bool,
    evidence: list[dict] | None = None,
) -> dict:
    dims = {
        "problem_severity": raw.problem_severity,
        "business_value": raw.business_value,
        "evidence_confidence": raw.evidence_confidence,
        "solution_fit": raw.solution_fit,
        "contactability": raw.contactability,
    }
    clamped = {k: max(0, min(_RANGES[k], int(v))) for k, v in dims.items()}

    # guard-rail: evidence_confidence is bounded by actual evidence strength
    ceiling = _evidence_ceiling(evidence or [])
    clamped["evidence_confidence"] = min(clamped["evidence_confidence"], ceiling)
    if not is_opportunity:
        clamped["problem_severity"] = min(clamped["problem_severity"], 10)

    total = sum(clamped.values())
    return {
        "scoring_version": SCORING_VERSION,
        **clamped,
        "total": total,
        "reasons": raw.reasons,
        "max_total": sum(_RANGES.values()),
    }
