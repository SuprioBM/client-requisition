"""Job queue with a pluggable backend.

Primary backend: Redis list with a reliable BLMOVE handoff (queue -> processing).
Job *state* always lives in Postgres; Redis only signals "work exists".

Dev fallback: if Redis is unreachable and APP_ENV != production, an in-process
asyncio queue is used and a loud warning is logged. This keeps the whole
pipeline runnable on a laptop with no Redis. In production a missing Redis is a
hard failure (RedisError).
"""

from __future__ import annotations

import asyncio
from typing import Protocol

from app.core.config import get_settings
from app.core.exceptions import RedisError
from app.core.logging import get_logger
from app.db.models.enums import JobStatus

log = get_logger(__name__)

QUEUE_KEY = "requisition:jobs:queue"
PROCESSING_KEY = "requisition:jobs:processing"


class QueueBackend(Protocol):
    async def enqueue(self, job_id: str) -> None: ...
    async def dequeue(self, timeout: int = 5) -> str | None: ...
    async def ack(self, job_id: str) -> None: ...
    async def requeue_stuck(self) -> list[str]: ...
    async def depth(self) -> int: ...
    @property
    def kind(self) -> str: ...


class RedisQueue:
    kind = "redis"

    async def enqueue(self, job_id: str) -> None:
        from app.core.redis import get_redis

        await get_redis().rpush(QUEUE_KEY, job_id)  # type: ignore[misc]
        log.info("queue.enqueued", job_id=job_id, backend="redis")

    async def dequeue(self, timeout: int = 5) -> str | None:
        from app.core.redis import get_redis

        return await get_redis().blmove(QUEUE_KEY, PROCESSING_KEY, timeout, "LEFT", "RIGHT")  # type: ignore[misc]

    async def ack(self, job_id: str) -> None:
        from app.core.redis import get_redis

        await get_redis().lrem(PROCESSING_KEY, 0, job_id)  # type: ignore[misc]

    async def requeue_stuck(self) -> list[str]:
        from app.core.redis import get_redis

        r = get_redis()
        moved: list[str] = []
        while True:
            item = await r.lmove(PROCESSING_KEY, QUEUE_KEY, "LEFT", "RIGHT")  # type: ignore[misc]
            if item is None:
                break
            moved.append(item)
        if moved:
            log.warning("queue.requeued_stuck", count=len(moved), job_ids=moved)
        return moved

    async def depth(self) -> int:
        from app.core.redis import get_redis

        return int(await get_redis().llen(QUEUE_KEY))  # type: ignore[misc]


class DbQueue:
    """Redis-free fallback: poll the jobs table for QUEUED work.

    Cross-process safe (unlike an in-memory queue) because the atomic
    `acquire_lease` UPDATE in JobRepository is the real claim. `enqueue` is a
    no-op: the job row already exists with status=QUEUED.
    """

    kind = "db_poll"

    async def enqueue(self, job_id: str) -> None:  # noqa: D401 - row already persisted
        log.info("queue.enqueued", job_id=job_id, backend="db_poll")

    async def dequeue(self, timeout: int = 5) -> str | None:
        from sqlalchemy import select

        from app.db.models.job import Job
        from app.db.session import session_scope

        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            async with session_scope() as s:
                stmt = (
                    select(Job.id)
                    .where(Job.status == JobStatus.QUEUED.value)
                    .order_by(Job.created_at.asc())
                    .limit(1)
                )
                job_id = (await s.execute(stmt)).scalar_one_or_none()
            if job_id is not None:
                return job_id
            if asyncio.get_event_loop().time() >= deadline:
                return None
            await asyncio.sleep(0.5)

    async def ack(self, job_id: str) -> None:
        return None

    async def requeue_stuck(self) -> list[str]:
        return []  # sweeper handles stale leases

    async def depth(self) -> int:
        from sqlalchemy import func, select

        from app.db.models.job import Job
        from app.db.session import session_scope

        async with session_scope() as s:
            return int(
                await s.scalar(
                    select(func.count()).select_from(Job).where(
                        Job.status == JobStatus.QUEUED.value
                    )
                )
                or 0
            )


_backend: QueueBackend | None = None


def set_queue_backend(backend: QueueBackend | None) -> None:
    global _backend
    _backend = backend


async def get_queue() -> QueueBackend:
    global _backend
    if _backend is not None:
        return _backend

    settings = get_settings()
    try:
        from app.core.redis import ping

        await ping()
        _backend = RedisQueue()
        log.info("queue.backend.selected", backend="redis")
        return _backend
    except Exception as exc:  # noqa: BLE001
        if settings.is_production:
            raise RedisError(
                "Redis is unreachable and APP_ENV=production requires it", cause=exc
            ) from exc
        _backend = DbQueue()
        log.warning(
            "queue.backend.fallback",
            backend="db_poll",
            reason=str(exc),
            note="dev fallback; polls the jobs table. Set REDIS_URL for push-based queueing.",
        )
        return _backend


# ---- convenience module-level wrappers (used by services / worker) ----
async def enqueue(job_id: str) -> None:
    await (await get_queue()).enqueue(job_id)


async def dequeue(timeout: int = 5) -> str | None:
    return await (await get_queue()).dequeue(timeout)


async def ack(job_id: str) -> None:
    await (await get_queue()).ack(job_id)


async def requeue_stuck() -> list[str]:
    return await (await get_queue()).requeue_stuck()


async def depth() -> int:
    return await (await get_queue()).depth()
