from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.dependencies import db_session, require_api_key
from app.db.models.enums import JobStatus
from app.db.repositories.jobs import JobRepository
from app.db.session import session_scope
from app.schemas.common import ok
from app.schemas.jobs import JobOut
from app.workers import queue

router = APIRouter()

_TERMINAL = {
    JobStatus.COMPLETED.value,
    JobStatus.COMPLETED_WITH_WARNINGS.value,
    JobStatus.FAILED.value,
    JobStatus.CANCELLED.value,
}


@router.get("")
async def list_jobs(
    session: AsyncSession = Depends(db_session),
    status: str | None = None,
    job_type: str | None = None,
    active_only: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    rows, total = await JobRepository(session).query(
        status=status, job_type=job_type, active_only=active_only, limit=limit, offset=offset
    )
    return ok(
        {
            "items": [JobOut.model_validate(j).model_dump() for j in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@router.get("/{job_id}")
async def get_job(job_id: str, session: AsyncSession = Depends(db_session)) -> dict:
    job = await JobRepository(session).get(job_id)
    return ok(JobOut.model_validate(job).model_dump())


@router.post("/{job_id}/cancel", dependencies=[Depends(require_api_key)])
async def cancel_job(job_id: str, session: AsyncSession = Depends(db_session)) -> dict:
    repo = JobRepository(session)
    job = await repo.get(job_id)
    await repo.transition(job, JobStatus.CANCELLED)
    await session.commit()
    return ok(JobOut.model_validate(job).model_dump())


@router.post("/{job_id}/retry", dependencies=[Depends(require_api_key)])
async def retry_job(job_id: str, session: AsyncSession = Depends(db_session)) -> dict:
    repo = JobRepository(session)
    job = await repo.get(job_id)
    await repo.retry(job)
    await session.commit()
    await queue.enqueue(job.id)
    return ok(JobOut.model_validate(job).model_dump())


@router.get("/{job_id}/stream")
async def stream_job(job_id: str, request: Request) -> EventSourceResponse:
    """Server-Sent Events: emits the job payload ~1x/sec until it reaches a
    terminal state, then a final `done` event. Cheap: one indexed PK read/sec."""

    async def _gen():  # type: ignore[no-untyped-def]
        last_serialized: str | None = None
        while True:
            if await request.is_disconnected():
                break
            async with session_scope() as s:
                job = await JobRepository(s).get_or_none(job_id)
            if job is None:
                yield {"event": "error", "data": json.dumps({"code": "JOB_NOT_FOUND"})}
                break
            payload = JobOut.model_validate(job).model_dump(mode="json")
            serialized = json.dumps(payload, default=str)
            if serialized != last_serialized:
                last_serialized = serialized
                yield {"event": "job", "data": serialized}
            if job.status in _TERMINAL:
                yield {"event": "done", "data": serialized}
                break
            await asyncio.sleep(1.0)

    return EventSourceResponse(_gen())
