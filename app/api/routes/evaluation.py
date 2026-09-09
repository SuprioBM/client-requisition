from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import db_session, require_api_key
from app.core.errors import ErrorCode
from app.core.exceptions import NotFoundError
from app.db.models.enums import JobType
from app.db.models.evaluation import EvaluationRun
from app.db.models.outreach import OutreachMessage
from app.db.models.prospect import Prospect
from app.db.repositories.evaluation import EvaluationRepository
from app.db.repositories.research import ResearchRepository
from app.schemas.common import ok
from app.services.job_service import create_and_enqueue

router = APIRouter()


class BulkEvalBody(BaseModel):
    prospect_ids: list[str] = Field(min_length=1, max_length=100)


@router.post("/bulk/evaluate", dependencies=[Depends(require_api_key)])
async def bulk_evaluate(body: BulkEvalBody, session: AsyncSession = Depends(db_session)) -> dict:
    jobs = []
    for pid in body.prospect_ids:
        if await session.get(Prospect, pid) is None:
            continue
        job = await create_and_enqueue(
            session, JobType.EVALUATION, {"prospect_id": pid}, prospect_id=pid
        )
        jobs.append({"prospect_id": pid, "job_id": job.id})
    return ok({"queued": jobs})


@router.post("/{prospect_id}/evaluate", dependencies=[Depends(require_api_key)])
async def start_evaluation(
    prospect_id: str, session: AsyncSession = Depends(db_session)
) -> dict:
    if await session.get(Prospect, prospect_id) is None:
        raise NotFoundError("Prospect not found", code=ErrorCode.NOT_FOUND)
    job = await create_and_enqueue(
        session, JobType.EVALUATION, {"prospect_id": prospect_id}, prospect_id=prospect_id
    )
    return ok({"job_id": job.id, "status": job.status})


@router.get("/{prospect_id}/evaluations")
async def evaluation_history(
    prospect_id: str, session: AsyncSession = Depends(db_session)
) -> dict:
    stmt = (
        select(EvaluationRun)
        .where(EvaluationRun.prospect_id == prospect_id)
        .order_by(desc(EvaluationRun.created_at))
        .options(selectinload(EvaluationRun.pain_points), selectinload(EvaluationRun.solutions))
    )
    runs = list((await session.execute(stmt)).scalars())
    return ok([_run_payload(r) for r in runs])


def _run_payload(run: EvaluationRun) -> dict:
    return {
        "evaluation_run_id": run.id,
        "prompt_version": run.prompt_version,
        "scoring_version": run.scoring_version,
        "model": run.model,
        "status": run.status,
        "is_opportunity": run.is_opportunity,
        "opportunity_summary": run.opportunity_summary,
        "opportunity_reasoning": run.opportunity_reasoning,
        "commercial_potential": run.commercial_potential,
        "score": run.score_breakdown,
        "pain_points": [
            {
                "id": pp.id,
                "category": pp.category,
                "title": pp.title,
                "description": pp.description,
                "confidence": pp.confidence,
                "evidence_ids": pp.evidence_ids,
            }
            for pp in run.pain_points
        ],
        "solutions": [
            {
                "service_category": s.service_category,
                "service_name": s.service_name,
                "why_it_fits": s.why_it_fits,
                "expected_value": s.expected_value,
                "confidence": s.confidence,
                "fit_rank": s.fit_rank,
                "pain_point_id": s.pain_point_id,
            }
            for s in sorted(run.solutions, key=lambda x: x.fit_rank)
        ],
        "completed_at": run.completed_at,
    }


@router.get("/{prospect_id}/evaluation")
async def get_evaluation(prospect_id: str, session: AsyncSession = Depends(db_session)) -> dict:
    run = await EvaluationRepository(session).latest(prospect_id)
    if run is None:
        raise NotFoundError("No evaluation for this prospect", code=ErrorCode.NOT_FOUND)
    return ok(_run_payload(run))


@router.get("/{prospect_id}/profile")
async def get_profile(prospect_id: str, session: AsyncSession = Depends(db_session)) -> dict:
    """Client intelligence profile (spec section 51)."""
    stmt = (
        select(Prospect)
        .where(Prospect.id == prospect_id)
        .options(selectinload(Prospect.sources), selectinload(Prospect.contacts))
    )
    prospect = (await session.execute(stmt)).scalar_one_or_none()
    if prospect is None:
        raise NotFoundError("Prospect not found", code=ErrorCode.NOT_FOUND)

    research = await ResearchRepository(session).latest_run(prospect_id)
    evaluation = await EvaluationRepository(session).latest(prospect_id)
    msgs = (
        await session.execute(
            select(OutreachMessage).where(OutreachMessage.prospect_id == prospect_id)
        )
    ).scalars().all()

    return ok(
        {
            "business": {
                "id": prospect.id,
                "name": prospect.business_name,
                "industry": prospect.industry,
                "location": {"city": prospect.city, "country": prospect.country,
                             "address": prospect.address},
                "website": prospect.website,
                "contact": {"phone": prospect.phone, "email": prospect.email},
                "rating": prospect.rating,
                "review_count": prospect.review_count,
                "status": prospect.status,
                "quality_status": prospect.quality_status,
            },
            "discovery": {
                "sources": [
                    {"provider": s.provider, "query": s.search_query, "url": s.source_url}
                    for s in prospect.sources
                ],
            },
            "research": None
            if research is None
            else {
                "website_status": research.website_status,
                "signals": research.signals,
                "social_profiles": research.social_profiles,
                "evidence": [
                    {
                        "id": e.id,
                        "type": e.evidence_type,
                        "source": e.source_type,
                        "source_url": e.source_url,
                        "observation": e.observation,
                        "confidence": e.confidence,
                        "data_origin": e.data_origin,
                        "collected_at": e.collected_at,
                    }
                    for e in research.evidence
                ],
            },
            "evaluation": None if evaluation is None else _run_payload(evaluation),
            "outreach": [
                {"id": m.id, "channel": m.channel, "status": m.status,
                 "subject": m.subject, "created_at": m.created_at}
                for m in msgs
            ],
        }
    )
