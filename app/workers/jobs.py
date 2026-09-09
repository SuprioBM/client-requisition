"""Job handlers. One per JobType. Invoked by the worker with an acquired lease."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from app.core.banners import job_failed_banner
from app.core.errors import ErrorCode, is_retryable
from app.core.exceptions import AppError
from app.core.logging import bind_contextvars, clear_contextvars, get_logger
from app.db.models.enums import JobStatus, JobType
from app.db.repositories.jobs import JobRepository
from app.db.session import session_scope
from app.workers import queue

log = get_logger(__name__)

Handler = Callable[[str], Awaitable[None]]
_HANDLERS: dict[str, Handler] = {}


def handler(job_type: JobType) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        _HANDLERS[job_type.value] = fn
        return fn

    return deco


def get_handler(job_type: str) -> Handler | None:
    return _HANDLERS.get(job_type)


async def _set_stage(job_id: str, stage: str, percent: int) -> None:
    async with session_scope() as s:
        job = await JobRepository(s).get_or_none(job_id)
        if job:
            job.current_stage = stage
            job.progress = {"stage": stage, "percent": percent}


async def run_job(job_id: str) -> None:
    """Dispatch + unified error handling / retry policy."""
    clear_contextvars()
    async with session_scope() as s:
        repo = JobRepository(s)
        job = await repo.get_or_none(job_id)
        if job is None:
            log.error("worker.job.missing", job_id=job_id)
            return
        job_type = job.job_type
        retry_count = job.retry_count
        max_retries = job.max_retries
        if job.status == JobStatus.QUEUED.value:
            # normal path: the worker already claimed the lease (RUNNING). This is
            # a safety net for direct invocation / requeued jobs.
            await repo.transition(job, JobStatus.RUNNING)
        elif job.status != JobStatus.RUNNING.value:
            log.warning("worker.job.not_runnable", job_id=job_id, status=job.status)
            return
    bind_contextvars(job_id=job_id, job_type=job_type)

    fn = get_handler(job_type)
    if fn is None:
        await _fail(job_id, ErrorCode.JOB_FAILED, f"no handler for job type {job_type}", None)
        return

    try:
        await fn(job_id)
    except AppError as exc:
        await _handle_failure(job_id, job_type, exc.code, str(exc.message), exc.context.get("stage"),
                              retry_count, max_retries, retryable=is_retryable(exc.code))
    except Exception as exc:  # noqa: BLE001
        log.error("worker.job.crashed", job_id=job_id, error=str(exc), exc_info=True)
        await _handle_failure(job_id, job_type, ErrorCode.INTERNAL_ERROR, str(exc), None,
                              retry_count, max_retries, retryable=True)
    finally:
        clear_contextvars()


async def _handle_failure(
    job_id: str,
    job_type: str,
    code: ErrorCode,
    message: str,
    stage: str | None,
    retry_count: int,
    max_retries: int,
    *,
    retryable: bool,
) -> None:
    if retryable and retry_count < max_retries:
        from app.core.config import get_settings

        cfg = get_settings()
        delay = min(
            cfg.max_retry_delay_seconds, cfg.retry_base_delay_seconds * 2**retry_count
        )
        async with session_scope() as s:
            repo = JobRepository(s)
            job = await repo.get(job_id)
            job.error_code = code.value
            job.error_message = message[:4000]
            await repo.prepare_retry(job)
        log.warning("worker.job.retry_scheduled", job_id=job_id, attempt=retry_count + 1,
                    delay_s=delay, error_code=code.value)
        await asyncio.sleep(delay)
        await queue.enqueue(job_id)
    else:
        await _fail(job_id, code, message, stage)


async def _fail(job_id: str, code: ErrorCode, message: str, stage: str | None) -> None:
    async with session_scope() as s:
        repo = JobRepository(s)
        job = await repo.get(job_id)
        job.current_stage = stage or job.current_stage
        await repo.mark_failed(job, code.value, message)
        job_type = job.job_type
    job_failed_banner(
        job_id=job_id, job_type=job_type, stage=stage, error_code=code.value,
        error_message=message,
        action="Inspect GET /api/v1/jobs/{id} for details\nFix the underlying cause, then POST /api/v1/jobs/{id}/retry",
    )
    log.error("worker.job.failed", job_id=job_id, error_code=code.value, stage=stage)


def register_handlers() -> None:
    """Import handler modules so their @handler decorators run. Call once at worker start."""
    from app.workers import (
        discovery_handler,  # noqa: F401
        evaluation_handler,  # noqa: F401
        research_handler,  # noqa: F401
    )
