from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import db_session, require_api_key
from app.core.logging import get_logger
from app.db.models.enums import JobType
from app.db.repositories.jobs import JobRepository
from app.discovery.planner import plan_queries
from app.schemas.common import ok
from app.schemas.discovery import DiscoverySearchRequest, QueryPlanOut
from app.schemas.jobs import JobOut
from app.services.job_service import create_and_enqueue

log = get_logger(__name__)
router = APIRouter()


@router.post("/search", dependencies=[Depends(require_api_key)])
async def start_discovery(
    payload: DiscoverySearchRequest,
    session: AsyncSession = Depends(db_session),
) -> dict:
    job = await create_and_enqueue(session, JobType.DISCOVERY, payload.model_dump())
    return ok({"job_id": job.id, "status": job.status})


@router.get("/jobs/{job_id}")
async def get_discovery_job(job_id: str, session: AsyncSession = Depends(db_session)) -> dict:
    job = await JobRepository(session).get(job_id)
    return ok(JobOut.model_validate(job).model_dump())


@router.post("/plan-preview")
async def preview_plan(payload: DiscoverySearchRequest) -> dict:
    plan = plan_queries(payload.industry, payload.city, payload.country)
    return ok(
        QueryPlanOut(
            industry=payload.industry,
            location_label=f"{payload.city}, {payload.country}",
            queries=plan,
        ).model_dump()
    )
