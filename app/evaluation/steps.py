"""LLM evaluation steps. Each returns (validated_model, llm_observability_dict)."""

from __future__ import annotations

from app.evaluation.llm import get_llm
from app.evaluation.prompts import (
    email_prompt,
    opportunity_prompt,
    outreach_strategy_prompt,
    pain_points_prompt,
    scoring_prompt,
    solution_mapping_prompt,
    whatsapp_prompt,
)
from app.schemas.evaluation import (
    EmailDraft,
    LeadScoreInput,
    OpportunityAssessment,
    OutreachStrategy,
    PainPointList,
    SolutionList,
    WhatsAppDraft,
)


async def detect_pain_points(
    prospect: dict, signals: dict, evidence: list[dict]
) -> tuple[PainPointList, dict]:
    return await get_llm().structured(
        "pain_points", PainPointList, pain_points_prompt(prospect, signals, evidence)
    )


async def map_solutions(prospect: dict, pain_points: list[dict]) -> tuple[SolutionList, dict]:
    if not pain_points:
        return SolutionList(solutions=[]), {"label": "solutions", "status": "skipped"}
    return await get_llm().structured(
        "solutions", SolutionList, solution_mapping_prompt(prospect, pain_points)
    )


async def evaluate_opportunity(
    prospect: dict, signals: dict, pain_points: list[dict], solutions: list[dict],
    evidence: list[dict],
) -> tuple[OpportunityAssessment, dict]:
    return await get_llm().structured(
        "opportunity",
        OpportunityAssessment,
        opportunity_prompt(prospect, signals, pain_points, solutions, evidence),
    )


async def propose_subscores(
    opportunity: dict, pain_points: list[dict], solutions: list[dict], signals: dict
) -> tuple[LeadScoreInput, dict]:
    return await get_llm().structured(
        "scoring", LeadScoreInput, scoring_prompt(opportunity, pain_points, solutions, signals)
    )


async def generate_strategy(
    prospect: dict, opportunity: dict, pain_points: list[dict], solutions: list[dict],
    evidence: list[dict],
) -> tuple[OutreachStrategy, dict]:
    return await get_llm().structured(
        "outreach_strategy",
        OutreachStrategy,
        outreach_strategy_prompt(prospect, opportunity, pain_points, solutions, evidence),
    )


async def generate_email(
    prospect: dict, strategy: dict, sender_name: str
) -> tuple[EmailDraft, dict]:
    return await get_llm().structured(
        "email", EmailDraft, email_prompt(prospect, strategy, sender_name)
    )


async def generate_whatsapp(
    prospect: dict, strategy: dict, sender_name: str
) -> tuple[WhatsAppDraft, dict]:
    return await get_llm().structured(
        "whatsapp", WhatsAppDraft, whatsapp_prompt(prospect, strategy, sender_name)
    )
