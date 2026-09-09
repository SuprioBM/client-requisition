from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.db.models.enums import JobStatus, JobType
from app.db.models.job import Job
from app.db.repositories.jobs import JobRepository
from app.db.session import session_scope
from app.services.job_service import create_and_enqueue


async def test_stale_running_job_is_detected_and_requeued():
    async with session_scope() as s:
        job = await create_and_enqueue(
            s, JobType.DISCOVERY, {"industry": "x", "city": "Dhaka", "country": "Bangladesh"}
        )
        jid = job.id

    # simulate a worker that claimed then crashed: RUNNING with an expired lease
    async with session_scope() as s:
        repo = JobRepository(s)
        j = await repo.get(jid)
        await repo.transition(j, JobStatus.RUNNING)
        j.lease_owner = "dead-worker"
        j.lease_expires_at = datetime.now(UTC) - timedelta(minutes=5)

    async with session_scope() as s:
        repo = JobRepository(s)
        stale = await repo.find_stale()
        assert any(x.id == jid for x in stale)
        for x in stale:
            x.lease_owner = None
            await repo.transition(x, JobStatus.QUEUED)

    async with session_scope() as s:
        j = await s.get(Job, jid)
        assert j.status == JobStatus.QUEUED.value


async def test_illegal_transition_is_rejected():
    from app.core.exceptions import JobError

    async with session_scope() as s:
        job = await create_and_enqueue(
            s, JobType.DISCOVERY, {"industry": "x", "city": "Dhaka", "country": "Bangladesh"}
        )
        repo = JobRepository(s)
        j = await repo.get(job.id)
        await repo.transition(j, JobStatus.RUNNING)
        await repo.transition(j, JobStatus.COMPLETED)
        try:
            await repo.transition(j, JobStatus.RUNNING)  # COMPLETED -> RUNNING illegal
            raised = False
        except JobError:
            raised = True
    assert raised
