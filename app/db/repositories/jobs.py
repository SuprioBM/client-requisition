from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ErrorCode
from app.core.exceptions import JobError, NotFoundError
from app.db.models.enums import JOB_TRANSITIONS, JobStatus, JobType
from app.db.models.job import Job


def _utcnow() -> datetime:
    return datetime.now(UTC)


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def create(
        self, job_type: JobType, params: dict, *, prospect_id: str | None = None, max_retries: int = 3
    ) -> Job:
        job = Job(
            job_type=job_type.value,
            status=JobStatus.QUEUED.value,
            params=params,
            prospect_id=prospect_id,
            max_retries=max_retries,
            progress={"stage": "QUEUED", "percent": 0},
        )
        self.s.add(job)
        await self.s.flush()
        return job

    async def get(self, job_id: str) -> Job:
        job = await self.s.get(Job, job_id)
        if job is None:
            raise NotFoundError(f"Job {job_id} not found", code=ErrorCode.JOB_NOT_FOUND)
        return job

    async def get_or_none(self, job_id: str) -> Job | None:
        return await self.s.get(Job, job_id)

    async def transition(self, job: Job, new: JobStatus) -> Job:
        current = JobStatus(job.status)
        if new != current and new not in JOB_TRANSITIONS.get(current, set()):
            raise JobError(
                f"Illegal job transition {current.value} -> {new.value}",
                code=ErrorCode.JOB_INVALID_STATE,
                context={"job_id": job.id},
            )
        job.status = new.value
        if new == JobStatus.RUNNING and job.started_at is None:
            job.started_at = _utcnow()
        if new in (
            JobStatus.COMPLETED,
            JobStatus.COMPLETED_WITH_WARNINGS,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        ):
            job.completed_at = _utcnow()
        await self.s.flush()
        return job

    async def acquire_lease(self, job_id: str, owner: str, lease_seconds: int) -> Job | None:
        """Atomically claim a QUEUED job for a worker. Returns None if already taken."""
        now = _utcnow()
        expires = now + timedelta(seconds=lease_seconds)
        res = await self.s.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == JobStatus.QUEUED.value)
            .values(
                status=JobStatus.RUNNING.value,
                lease_owner=owner,
                lease_expires_at=expires,
                heartbeat_at=now,
                started_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        await self.s.flush()
        if res.rowcount == 0:
            return None
        return await self.s.get(Job, job_id)

    async def heartbeat(self, job: Job, lease_seconds: int) -> None:
        now = _utcnow()
        job.heartbeat_at = now
        job.lease_expires_at = now + timedelta(seconds=lease_seconds)
        await self.s.flush()

    async def find_stale(self, older_than_seconds: int = 0) -> list[Job]:
        now = _utcnow()
        stmt = select(Job).where(
            Job.status == JobStatus.RUNNING.value,
            Job.lease_expires_at.is_not(None),
            Job.lease_expires_at < now,
        )
        return list((await self.s.execute(stmt)).scalars())

    async def mark_failed(self, job: Job, code: str, message: str) -> Job:
        job.error_code = code
        job.error_message = message[:4000]
        return await self.transition(job, JobStatus.FAILED)

    async def prepare_retry(self, job: Job) -> bool:
        if job.retry_count >= job.max_retries:
            return False
        job.retry_count += 1
        job.lease_owner = None
        job.lease_expires_at = None
        await self.transition(job, JobStatus.QUEUED)
        return True
