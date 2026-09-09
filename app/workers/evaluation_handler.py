from __future__ import annotations

from app.core.errors import ErrorCode
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.db.models.enums import JobStatus, JobType
from app.db.repositories.jobs import JobRepository
from app.db.session import session_scope
from app.graphs.checkpointer import checkpointer_scope
from app.graphs.evaluation_graph import EVALUATION_STAGES, build_evaluation_graph
from app.workers.jobs import _set_stage, handler

log = get_logger(__name__)


async def _persist_progress(job_id: str, state: dict) -> None:
    stage = state.get("stage")
    if not stage:
        return
    try:
        idx = EVALUATION_STAGES.index(stage)
        percent = int(5 + (idx + 1) / len(EVALUATION_STAGES) * 90)
    except ValueError:
        percent = None
    async with session_scope() as s:
        job = await JobRepository(s).get_or_none(job_id)
        if job is None:
            return
        job.current_stage = stage
        prog: dict = {"stage": stage, "percent": percent}
        prog["counters"] = {
            "evidence": len(state.get("evidence", [])),
            "pain_points": len(state.get("pain_points", [])),
            "solutions": len(state.get("solutions", [])),
        }
        job.progress = prog


@handler(JobType.EVALUATION)
async def run_evaluation_job(job_id: str) -> None:
    async with session_scope() as s:
        job = await JobRepository(s).get(job_id)
        prospect_id = job.prospect_id or dict(job.params).get("prospect_id")

    if not prospect_id:
        raise AppError("evaluation job has no prospect_id", code=ErrorCode.VALIDATION_ERROR)

    await _set_stage(job_id, "EVALUATING", 20)

    initial: dict = {
        "job_id": job_id,
        "prospect_id": prospect_id,
        "evidence": [],
        "warnings": [],
        "errors": [],
    }
    final_state: dict = {}
    async with checkpointer_scope() as cp:
        graph = build_evaluation_graph(checkpointer=cp)
        config = {"configurable": {"thread_id": job_id}, "recursion_limit": 50}
        async for chunk in graph.astream(initial, config=config, stream_mode="values"):
            final_state = chunk
            await _persist_progress(job_id, chunk)

    if final_state.get("errors"):
        raise AppError(
            final_state["errors"][0].get("message", "evaluation error"),
            code=ErrorCode.LLM_INVALID_OUTPUT,
            context={"stage": final_state.get("stage")},
        )

    result = {
        "prospect_id": prospect_id,
        "evaluation_run_id": final_state.get("evaluation_run_id"),
        "research_run_id": final_state.get("research_run_id"),
        "is_opportunity": (final_state.get("opportunity") or {}).get("is_opportunity"),
        "score_total": {k: v for k, v in (final_state.get("score") or {}).items()
                        if k != "_signals"}.get("total"),
        "pain_points": len(final_state.get("pain_points", [])),
        "solutions": len(final_state.get("solutions", [])),
        "approval_status": final_state.get("approval_status"),
        "outreach_messages": (final_state.get("email_draft") or {}).get("_message_ids", []),
    }

    async with session_scope() as s:
        repo = JobRepository(s)
        job = await repo.get(job_id)
        job.result = result
        job.warnings = final_state.get("warnings", [])
        job.current_stage = "COMPLETED"
        job.progress = {"stage": "COMPLETED", "percent": 100}
        status = JobStatus.COMPLETED_WITH_WARNINGS if job.warnings else JobStatus.COMPLETED
        await repo.transition(job, status)

    log.info("evaluation.job.completed", job_id=job_id, prospect_id=prospect_id,
             score=result["score_total"], is_opportunity=result["is_opportunity"])
