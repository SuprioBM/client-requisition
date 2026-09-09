from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import db_session, require_api_key
from app.core.errors import ErrorCode
from app.core.exceptions import NotFoundError
from app.db.models.enums import JobType
from app.db.models.prospect import Prospect
from app.db.repositories.research import ResearchRepository
from app.schemas.common import ok
from app.services.job_service import create_and_enqueue

router = APIRouter()


class BulkBody(BaseModel):
    prospect_ids: list[str] = Field(min_length=1, max_length=100)
    force: bool = False


@router.post("/bulk/research", dependencies=[Depends(require_api_key)])
async def bulk_research(body: BulkBody, session: AsyncSession = Depends(db_session)) -> dict:
    jobs = []
    for pid in body.prospect_ids:
        if await session.get(Prospect, pid) is None:
            continue
        job = await create_and_enqueue(
            session, JobType.RESEARCH, {"prospect_id": pid, "force": body.force}, prospect_id=pid
        )
        jobs.append({"prospect_id": pid, "job_id": job.id})
    return ok({"queued": jobs})


@router.post("/{prospect_id}/research", dependencies=[Depends(require_api_key)])
async def start_research(
    prospect_id: str, force: bool = False, session: AsyncSession = Depends(db_session)
) -> dict:
    if await session.get(Prospect, prospect_id) is None:
        raise NotFoundError("Prospect not found", code=ErrorCode.NOT_FOUND)
    job = await create_and_enqueue(
        session, JobType.RESEARCH, {"prospect_id": prospect_id, "force": force},
        prospect_id=prospect_id,
    )
    return ok({"job_id": job.id, "status": job.status})


@router.get("/{prospect_id}/research")
async def get_research(prospect_id: str, session: AsyncSession = Depends(db_session)) -> dict:
    run = await ResearchRepository(session).latest_run(prospect_id)
    if run is None:
        raise NotFoundError("No research run for this prospect", code=ErrorCode.NOT_FOUND)
    return ok(
        {
            "research_run_id": run.id,
            "status": run.status,
            "schema_version": run.schema_version,
            "website_status": run.website_status,
            "website_final_url": run.website_final_url,
            "sources_used": run.sources_used,
            "signals": run.signals,
            "social_profiles": run.social_profiles,
            "completed_at": run.completed_at,
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
                for e in run.evidence
            ],
        }
    )
