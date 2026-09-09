from __future__ import annotations

from app.core.logging import get_logger
from app.db.models.enums import JobStatus, JobType
from app.db.repositories.jobs import JobRepository
from app.db.session import session_scope
from app.services.research_service import run_research
from app.workers.jobs import _set_stage, handler

log = get_logger(__name__)


@handler(JobType.RESEARCH)
async def run_research_job(job_id: str) -> None:
    async with session_scope() as s:
        job = await JobRepository(s).get(job_id)
        params = dict(job.params)
        prospect_id = job.prospect_id or params.get("prospect_id")

    if not prospect_id:
        from app.core.errors import ErrorCode
        from app.core.exceptions import AppError

        raise AppError("research job has no prospect_id", code=ErrorCode.VALIDATION_ERROR)

    await _set_stage(job_id, "RESEARCHING", 30)
    result = await run_research(prospect_id, job_id=job_id, force=params.get("force", False))

    async with session_scope() as s:
        repo = JobRepository(s)
        job = await repo.get(job_id)
        job.result = result
        job.current_stage = "COMPLETED"
        job.progress = {"stage": "COMPLETED", "percent": 100}
        await repo.transition(job, JobStatus.COMPLETED)
    log.info("research.job.completed", job_id=job_id, prospect_id=prospect_id)
