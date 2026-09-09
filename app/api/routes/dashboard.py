from __future__ import annotations

from collections import Counter, defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import db_session
from app.core import redis as redis_mod
from app.core.config import get_settings
from app.db import session as db
from app.db.models.enums import JobStatus, JobType, OutreachStatus, ProspectStatus
from app.db.models.evaluation import EvaluationRun
from app.db.models.job import Job
from app.db.models.outreach import AuditEvent, OutreachEvent, OutreachMessage
from app.db.models.prospect import Prospect
from app.schemas.common import ok

router = APIRouter()


@router.get("/health")
async def dashboard_health() -> dict:
    """Component health for the status bar."""
    settings = get_settings()
    checks: dict[str, str] = {}
    try:
        await db.ping()
        checks["database"] = "online"
    except Exception:  # noqa: BLE001
        checks["database"] = "offline"
    try:
        await redis_mod.ping()
        checks["redis"] = "online"
    except Exception:  # noqa: BLE001
        checks["redis"] = "degraded"  # dev fallback to DB-poll queue still works
    checks["api"] = "online"
    # worker: infer from a recent heartbeat on any RUNNING job, else "unknown"
    async with db.session_scope() as s:
        running = await s.scalar(
            select(func.count()).select_from(Job).where(Job.status == JobStatus.RUNNING.value)
        )
    checks["worker"] = "online" if settings.embedded_worker_enabled() or running else "unknown"
    return ok({"components": checks, "env": settings.app_env.value,
               "capabilities": settings.capability_summary()})


@router.get("/stats")
async def dashboard_stats(session: AsyncSession = Depends(db_session)) -> dict:
    async def _count(model, *where) -> int:
        stmt = select(func.count()).select_from(model)
        for w in where:
            stmt = stmt.where(w)
        return int(await session.scalar(stmt) or 0)

    prospect_by_status = {
        row[0]: int(row[1])
        for row in await session.execute(
            select(Prospect.status, func.count()).group_by(Prospect.status)
        )
    }
    job_by_status = {
        row[0]: int(row[1])
        for row in await session.execute(select(Job.status, func.count()).group_by(Job.status))
    }
    outreach_by_status = {
        row[0]: int(row[1])
        for row in await session.execute(
            select(OutreachMessage.status, func.count()).group_by(OutreachMessage.status)
        )
    }

    high_opp = await _count(EvaluationRun, EvaluationRun.score_total >= 70)
    researched_total = await _count(Prospect, Prospect.last_researched_at.is_not(None))
    evaluated_total = await _count(Prospect, Prospect.last_evaluated_at.is_not(None))

    return ok(
        {
            "prospects": {
                "total": sum(prospect_by_status.values()),
                "by_status": prospect_by_status,
                "new": prospect_by_status.get(ProspectStatus.DISCOVERED.value, 0),
                "researching": researched_total,
                "evaluating": prospect_by_status.get(ProspectStatus.EVALUATING.value, 0),
                "evaluated": evaluated_total,
                "outreach_ready": prospect_by_status.get(ProspectStatus.OUTREACH_DRAFTED.value, 0)
                + prospect_by_status.get(ProspectStatus.OUTREACH_APPROVED.value, 0),
                "contacted": prospect_by_status.get(ProspectStatus.CONTACTED.value, 0),
            },
            "opportunities": {
                "high": high_opp,
                "evaluations_total": await _count(EvaluationRun),
            },
            "outreach": {
                "by_status": outreach_by_status,
                "awaiting_approval": outreach_by_status.get(
                    OutreachStatus.PENDING_APPROVAL.value, 0
                ),
                "approved": outreach_by_status.get(OutreachStatus.APPROVED.value, 0),
                "sent": outreach_by_status.get(OutreachStatus.SENT.value, 0),
            },
            "jobs": {
                "by_status": job_by_status,
                "active": job_by_status.get(JobStatus.QUEUED.value, 0)
                + job_by_status.get(JobStatus.RUNNING.value, 0),
                "failed": job_by_status.get(JobStatus.FAILED.value, 0),
            },
        }
    )


@router.get("/activity")
async def dashboard_activity(
    session: AsyncSession = Depends(db_session), limit: int = Query(40, ge=1, le=200)
) -> dict:
    events: list[dict] = []

    for ev in (
        await session.execute(
            select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)
        )
    ).scalars():
        events.append(
            {
                "at": ev.created_at,
                "kind": "audit",
                "actor": ev.actor,
                "message": f"{ev.action}",
                "entity_type": ev.entity_type,
                "entity_id": ev.entity_id,
                "detail": ev.detail,
            }
        )

    for oe in (
        await session.execute(
            select(OutreachEvent).order_by(OutreachEvent.created_at.desc()).limit(limit)
        )
    ).scalars():
        events.append(
            {
                "at": oe.created_at,
                "kind": "outreach",
                "message": f"outreach {oe.event_type}",
                "entity_type": "outreach_message",
                "entity_id": oe.message_id,
                "detail": oe.detail,
            }
        )

    for job in (
        await session.execute(select(Job).order_by(Job.updated_at.desc()).limit(limit))
    ).scalars():
        msg = f"{job.job_type.lower()} job {job.status.lower()}"
        if job.current_stage:
            msg += f" ({job.current_stage})"
        events.append(
            {
                "at": job.updated_at,
                "kind": "job",
                "message": msg,
                "entity_type": "job",
                "entity_id": job.id,
                "detail": {"error_code": job.error_code} if job.error_code else {},
            }
        )

    events.sort(key=lambda e: e["at"], reverse=True)
    return ok(events[:limit])


@router.get("/analytics/providers")
async def provider_analytics(session: AsyncSession = Depends(db_session)) -> dict:
    """Aggregate discovery provider metadata stored on completed jobs."""
    jobs = (
        await session.execute(
            select(Job).where(Job.job_type == JobType.DISCOVERY.value)
        )
    ).scalars()
    agg: dict[str, dict] = defaultdict(
        lambda: {"runs": 0, "ok": 0, "failed": 0, "skipped": 0, "results": 0, "duration_ms": 0}
    )
    for job in jobs:
        for run in (job.result or {}).get("provider_runs", []):
            p = agg[run.get("provider", "unknown")]
            p["runs"] += 1
            p["results"] += run.get("result_count", 0) or 0
            p["duration_ms"] += run.get("duration_ms", 0) or 0
            status = run.get("status", "")
            if status in ("ok", "partial"):
                p["ok"] += 1
            elif status == "failed":
                p["failed"] += 1
            elif status == "skipped":
                p["skipped"] += 1
    out = []
    for provider, p in agg.items():
        attempted = p["ok"] + p["failed"]
        out.append(
            {
                "provider": provider,
                "runs": p["runs"],
                "results": p["results"],
                "success_rate": round(p["ok"] / attempted, 3) if attempted else None,
                "avg_duration_ms": round(p["duration_ms"] / p["runs"]) if p["runs"] else None,
                "failed": p["failed"],
                "skipped": p["skipped"],
            }
        )
    out.sort(key=lambda x: x["results"], reverse=True)
    return ok(out)


@router.get("/settings")
async def dashboard_settings() -> dict:
    """Non-secret runtime configuration for the Settings page. No API keys."""
    s = get_settings()
    return ok(
        {
            "app_env": s.app_env.value,
            "groq_model": s.groq_model,
            "max_queries_per_plan": s.max_queries_per_plan,
            "discovery_provider_concurrency": s.discovery_provider_concurrency,
            "research_concurrency": s.research_concurrency,
            "research_http_timeout_seconds": s.research_http_timeout_seconds,
            "research_cache_ttl_seconds": s.research_cache_ttl_seconds,
            "playwright_enabled": s.playwright_enabled,
            "worker_job_lease_seconds": s.worker_job_lease_seconds,
            "embedded_worker": s.embedded_worker_enabled(),
            "capabilities": s.capability_summary(),
        }
    )


@router.get("/analytics/research")
async def research_analytics(session: AsyncSession = Depends(db_session)) -> dict:
    from app.db.models.research import ResearchRun

    runs = (await session.execute(select(ResearchRun))).scalars().all()
    status_counts: Counter = Counter(r.status for r in runs)
    website_counts: Counter = Counter(r.website_status for r in runs if r.website_status)
    source_counts: Counter = Counter(src for r in runs for src in (r.sources_used or []))
    return ok(
        {
            "total": len(runs),
            "by_status": dict(status_counts),
            "by_website_status": dict(website_counts),
            "source_usage": dict(source_counts),
        }
    )
