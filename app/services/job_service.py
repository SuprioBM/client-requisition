from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import RedisError
from app.core.logging import get_logger
from app.db.models.enums import JobType
from app.db.models.job import Job
from app.db.repositories.jobs import JobRepository
from app.workers import queue

log = get_logger(__name__)


async def create_and_enqueue(
    session: AsyncSession,
    job_type: JobType,
    params: dict,
    *,
    prospect_id: str | None = None,
) -> Job:
    repo = JobRepository(session)
    job = await repo.create(job_type, params, prospect_id=prospect_id)
    await session.commit()
    try:
        await queue.enqueue(job.id)
    except Exception as exc:  # keep the job row; surface the infra failure
        log.error("job.enqueue.failed", job_id=job.id, error=str(exc))
        raise RedisError("Could not enqueue job", cause=exc) from exc
    log.info("job.created", job_id=job.id, job_type=job_type.value, prospect_id=prospect_id)
    return job
