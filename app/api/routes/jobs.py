from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import db_session
from app.db.models.enums import JobStatus
from app.db.repositories.jobs import JobRepository
from app.schemas.common import ok
from app.schemas.jobs import JobOut

router = APIRouter()


@router.get("/{job_id}")
async def get_job(job_id: str, session: AsyncSession = Depends(db_session)) -> dict:
    job = await JobRepository(session).get(job_id)
    return ok(JobOut.model_validate(job).model_dump())


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str, session: AsyncSession = Depends(db_session)) -> dict:
    repo = JobRepository(session)
    job = await repo.get(job_id)
    await repo.transition(job, JobStatus.CANCELLED)
    await session.commit()
    return ok(JobOut.model_validate(job).model_dump())
