"""Pydantic schemas for LLM structured output. Every LLM response is validated
against one of these; invalid output triggers a bounded, constrained retry.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Confidence = Literal["CONFIRMED", "LIKELY", "POSSIBLE", "NOT_ENOUGH_EVIDENCE"]
PainCategory = Literal[
    "WEBSITE", "AUTOMATION", "AI", "BUSINESS_PROCESS", "ONLINE_PRESENCE", "CUSTOM_SOFTWARE"
]
Commercial = Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"]


class PainPoint(BaseModel):
    category: PainCategory
    title: str = Field(max_length=160)
    description: str = Field(max_length=1200)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: Confidence

    @field_validator("evidence_ids")
    @classmethod
    def _dedupe(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(v))


class PainPointList(BaseModel):
    pain_points: list[PainPoint] = Field(default_factory=list, max_length=8)


class SolutionRecommendation(BaseModel):
    pain_point_title: str
    service_category: str
    service_name: str
    why_it_fits: str = Field(max_length=800)
    expected_value: str = Field(max_length=800)
    confidence: Confidence
    fit_rank: int = Field(ge=1, le=20)


class SolutionList(BaseModel):
    solutions: list[SolutionRecommendation] = Field(default_factory=list, max_length=10)


class OpportunityAssessment(BaseModel):
    is_opportunity: bool
    summary: str = Field(max_length=1200)
    reasoning: str = Field(max_length=2000)
    commercial_potential: Commercial
    contactable: bool
    outreach_worthwhile: bool


class LeadScoreInput(BaseModel):
    """Sub-scores proposed by the LLM. Code clamps + sums -> deterministic total."""

    problem_severity: int = Field(ge=0, le=25)
    business_value: int = Field(ge=0, le=25)
    evidence_confidence: int = Field(ge=0, le=20)
    solution_fit: int = Field(ge=0, le=20)
    contactability: int = Field(ge=0, le=10)
    reasons: dict[str, str] = Field(default_factory=dict)


class OutreachStrategy(BaseModel):
    primary_observation: str = Field(max_length=600)
    primary_problem: str = Field(max_length=400)
    primary_solution: str = Field(max_length=400)
    value_proposition: str = Field(max_length=600)
    tone: str = Field(max_length=120)
    call_to_action: str = Field(max_length=300)
    evidence_ids: list[str] = Field(default_factory=list)


class EmailDraft(BaseModel):
    subject: str = Field(max_length=160)
    body: str = Field(max_length=2400)


class WhatsAppDraft(BaseModel):
    body: str = Field(max_length=900)
