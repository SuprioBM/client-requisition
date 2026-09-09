from __future__ import annotations

from app.core.errors import ErrorCode
from app.core.exceptions import AppError, JobError
from app.core.logging import get_logger
from app.db.models.enums import JobStatus, JobType
from app.db.repositories.jobs import JobRepository
from app.db.session import session_scope
from app.graphs.checkpointer import checkpointer_scope
from app.graphs.discovery_graph import DISCOVERY_STAGES, build_discovery_graph
from app.workers.jobs import _set_stage, handler

log = get_logger(__name__)


async def _persist_progress(job_id: str, state: dict) -> None:
    """Push the current graph node + partial results onto the job row so the
    dashboard SSE stream shows live pipeline progress."""
    stage = state.get("stage")
    if not stage:
        return
    try:
        idx = DISCOVERY_STAGES.index(stage)
        percent = int(5 + (idx + 1) / len(DISCOVERY_STAGES) * 90)
    except ValueError:
        percent = None
    async with session_scope() as s:
        job = await JobRepository(s).get_or_none(job_id)
        if job is None:
            return
        job.current_stage = stage
        prog = {"stage": stage, "percent": percent}
        if state.get("provider_runs"):
            prog["provider_runs"] = state["provider_runs"]
        if state.get("summary"):
            prog["counters"] = {
                k: state["summary"].get(k)
                for k in ("raw_candidates", "unique_clusters", "prospects_created")
                if state["summary"].get(k) is not None
            }
        job.progress = prog


@handler(JobType.DISCOVERY)
async def run_discovery_job(job_id: str) -> None:
    async with session_scope() as s:
        job = await JobRepository(s).get(job_id)
        params = dict(job.params)

    await _set_stage(job_id, "DISCOVERING", 5)

    initial = {
        "job_id": job_id,
        "industry": params["industry"],
        "city": params["city"],
        "country": params["country"],
        "radius_km": float(params.get("radius_km", 10.0)),
        "target_leads": int(params.get("target_leads", 60)),
        "provider_runs": [],
        "candidates": [],
        "warnings": [],
        "errors": [],
    }

    final_state: dict = {}
    async with checkpointer_scope() as cp:
        graph = build_discovery_graph(checkpointer=cp)
        config = {"configurable": {"thread_id": job_id}, "recursion_limit": 50}
        async for chunk in graph.astream(initial, config=config, stream_mode="values"):
            final_state = chunk
            await _persist_progress(job_id, chunk)

    errors = final_state.get("errors", [])
    if errors:
        raise JobError(
            errors[0].get("message", "discovery graph error"),
            code=ErrorCode.VALIDATION_ERROR,
            context={"stage": final_state.get("stage")},
        )

    summary = final_state.get("summary", {})
    warnings = final_state.get("warnings", [])
    any_ok = summary.get("any_provider_succeeded", False)

    if not any_ok and summary.get("prospects_created", 0) == 0:
        async with session_scope() as s:
            job = await JobRepository(s).get(job_id)
            job.result = summary
            job.warnings = warnings
        raise AppError(
            "discovery_providers_unavailable: every attempted provider failed",
            code=ErrorCode.PROVIDER_UNAVAILABLE,
            context={"stage": "aggregate"},
        )

    async with session_scope() as s:
        repo = JobRepository(s)
        job = await repo.get(job_id)
        job.result = summary
        job.warnings = warnings
        job.current_stage = "COMPLETED"
        job.progress = {"stage": "COMPLETED", "percent": 100}
        status = JobStatus.COMPLETED_WITH_WARNINGS if warnings else JobStatus.COMPLETED
        await repo.transition(job, status)

    log.info(
        "discovery.job.completed",
        job_id=job_id,
        created=summary.get("prospects_created"),
        updated=summary.get("prospects_updated"),
        warnings=len(warnings),
    )
