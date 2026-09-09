"""Background worker entrypoint:  python -m app.workers.worker

- Requeues anything stranded in the processing list on startup.
- BLMOVE/await dequeue -> claim job via atomic DB lease -> run handler.
- Heartbeats the lease while the handler runs.
- A sweeper requeues jobs whose lease expired (crashed worker recovery).
- Graceful shutdown on SIGINT/SIGTERM: finishes the in-flight job, then exits.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import socket
import uuid

from app.core.config import validate_runtime
from app.core.logging import configure_logging, get_logger
from app.db.models.enums import JobStatus
from app.db.repositories.jobs import JobRepository
from app.db.session import dispose_engine, session_scope
from app.workers import queue
from app.workers.jobs import register_handlers, run_job

log = get_logger("app.worker")

WORKER_ID = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
_shutdown = asyncio.Event()


async def _heartbeat(job_id: str, lease_seconds: int) -> None:
    interval = max(5, lease_seconds // 3)
    while True:
        await asyncio.sleep(interval)
        try:
            async with session_scope() as s:
                repo = JobRepository(s)
                job = await repo.get_or_none(job_id)
                if job and job.status == JobStatus.RUNNING.value:
                    await repo.heartbeat(job, lease_seconds)
        except Exception as exc:  # noqa: BLE001
            log.warning("worker.heartbeat.failed", job_id=job_id, error=str(exc))


async def _sweeper(lease_seconds: int) -> None:
    while not _shutdown.is_set():
        await asyncio.sleep(max(30, lease_seconds // 2))
        try:
            async with session_scope() as s:
                repo = JobRepository(s)
                stale = await repo.find_stale()
                for job in stale:
                    log.warning("worker.stale_job.recovered", job_id=job.id,
                                lease_owner=job.lease_owner)
                    job.lease_owner = None
                    job.lease_expires_at = None
                    await repo.transition(job, JobStatus.QUEUED)
                    await queue.enqueue(job.id)
        except Exception as exc:  # noqa: BLE001
            log.warning("worker.sweeper.failed", error=str(exc))


async def _process_one(job_id: str, lease_seconds: int) -> None:
    async with session_scope() as s:
        claimed = await JobRepository(s).acquire_lease(job_id, WORKER_ID, lease_seconds)
    if claimed is None:
        log.info("worker.job.already_claimed", job_id=job_id)
        await queue.ack(job_id)
        return

    hb = asyncio.create_task(_heartbeat(job_id, lease_seconds))
    try:
        await run_job(job_id)
    finally:
        hb.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await hb
        await queue.ack(job_id)


async def main(*, install_signal_handlers: bool = True, dispose_on_exit: bool = True) -> None:
    configure_logging()
    settings = validate_runtime()
    register_handlers()
    lease_seconds = settings.worker_job_lease_seconds
    _shutdown.clear()

    if install_signal_handlers:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, _shutdown.set)

    q = await queue.get_queue()
    log.info("worker.started", worker_id=WORKER_ID, queue_backend=q.kind,
             env=settings.app_env.value)

    requeued = await queue.requeue_stuck()
    if requeued:
        log.warning("worker.startup.requeued", count=len(requeued))

    sweeper = asyncio.create_task(_sweeper(lease_seconds))
    try:
        while not _shutdown.is_set():
            job_id = await queue.dequeue(timeout=5)
            if job_id is None:
                continue
            log.info("worker.job.received", job_id=job_id)
            try:
                await _process_one(job_id, lease_seconds)
            except Exception as exc:  # noqa: BLE001 - never let the loop die
                log.error("worker.process.error", job_id=job_id, error=str(exc), exc_info=True)
                with contextlib.suppress(Exception):
                    await queue.ack(job_id)
    finally:
        sweeper.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sweeper
        if dispose_on_exit:
            await dispose_engine()
        log.info("worker.stopped", worker_id=WORKER_ID)


if __name__ == "__main__":
    asyncio.run(main())
