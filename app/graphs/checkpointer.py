"""LangGraph checkpointer selection.

- testing / no config  -> MemorySaver (fast, ephemeral)
- LANGGRAPH_CHECKPOINT_DB = sqlite path or empty -> AsyncSqliteSaver (survives restarts, single worker)
- LANGGRAPH_CHECKPOINT_DB = postgresql://... -> AsyncPostgresSaver (multi-worker safe)

Job-level resumability does NOT depend on this: worker handlers persist stage
results to Postgres and skip completed stages on retry. The checkpointer is an
additional safety net keyed by thread_id == job_id.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.core.config import AppEnv, get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

_DEFAULT_SQLITE = ".langgraph_checkpoints.sqlite"


@asynccontextmanager
async def checkpointer_scope() -> AsyncIterator[object]:
    settings = get_settings()

    if settings.app_env == AppEnv.testing:
        from langgraph.checkpoint.memory import MemorySaver

        yield MemorySaver()
        return

    target = settings.langgraph_checkpoint_db or ""
    if target.startswith(("postgresql://", "postgres://")):
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

            async with AsyncPostgresSaver.from_conn_string(target) as cp:
                await cp.setup()
                log.info("checkpointer.selected", kind="postgres")
                yield cp
                return
        except Exception as exc:  # noqa: BLE001
            log.warning("checkpointer.postgres.failed", error=str(exc), fallback="sqlite")

    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        path = target if target.endswith((".sqlite", ".db")) else _DEFAULT_SQLITE
        async with AsyncSqliteSaver.from_conn_string(path) as cp:
            log.info("checkpointer.selected", kind="sqlite", path=path)
            yield cp
    except Exception as exc:  # noqa: BLE001
        from langgraph.checkpoint.memory import MemorySaver

        log.warning("checkpointer.sqlite.failed", error=str(exc), fallback="memory")
        yield MemorySaver()
