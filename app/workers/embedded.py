"""Run the worker loop as an asyncio task inside the API process (dev convenience).

Enabled by default outside production so `uvicorn app.main:app` runs the full
pipeline with no separate worker process. Disable with RUN_EMBEDDED_WORKER=false
and run `python -m app.workers.worker` instead.
"""

from __future__ import annotations

import asyncio
import contextlib

from app.core.logging import get_logger

log = get_logger("app.worker.embedded")

_task: asyncio.Task | None = None


async def start() -> None:
    global _task
    if _task is not None:
        return
    from app.workers import worker

    async def _runner() -> None:
        try:
            await worker.main(install_signal_handlers=False, dispose_on_exit=False)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.error("embedded_worker.crashed", error=str(exc), exc_info=True)

    _task = asyncio.create_task(_runner(), name="embedded-worker")
    log.info("embedded_worker.started")


async def stop() -> None:
    global _task
    if _task is None:
        return
    from app.workers.worker import _shutdown

    _shutdown.set()
    _task.cancel()
    with contextlib.suppress(TimeoutError, asyncio.CancelledError):
        await asyncio.wait_for(_task, timeout=10)
    _task = None
    log.info("embedded_worker.stopped")
