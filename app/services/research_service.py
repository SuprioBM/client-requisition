"""Research a prospect: cache check -> orchestrate -> persist ResearchRun + Evidence."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.core.errors import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.logging import bind_contextvars, get_logger
from app.db.models.prospect import Prospect
from app.db.repositories.research import ResearchRepository
from app.db.session import session_scope
from app.research.orchestrator import research_prospect

log = get_logger(__name__)


def _prospect_to_dict(p: Prospect) -> dict[str, Any]:
    return {
        "id": p.id,
        "business_name": p.business_name,
        "city": p.city,
        "country": p.country,
        "website": p.website,
        "phone": p.phone,
        "email": p.email,
        "rating": p.rating,
        "review_count": p.review_count,
        "provider_metadata": p.provider_metadata or {},
    }


async def run_research(
    prospect_id: str, *, job_id: str | None = None, force: bool = False
) -> dict[str, Any]:
    bind_contextvars(prospect_id=prospect_id, stage="research")
    settings = get_settings()

    async with session_scope() as s:
        prospect = await s.get(Prospect, prospect_id)
        if prospect is None:
            raise NotFoundError(f"Prospect {prospect_id} not found", code=ErrorCode.NOT_FOUND)
        pdict = _prospect_to_dict(prospect)

        repo = ResearchRepository(s)
        if not force:
            fresh = await repo.fresh_run(prospect_id, settings.research_cache_ttl_seconds)
            if fresh is not None:
                log.info("research.cache.hit", prospect_id=prospect_id, run_id=fresh.id)
                return {
                    "research_run_id": fresh.id,
                    "status": fresh.status,
                    "cached": True,
                    "website_status": fresh.website_status,
                    "evidence_count": len(fresh.evidence),
                    "signals": fresh.signals,
                }

    outcome = await research_prospect(pdict)

    async with session_scope() as s:
        repo = ResearchRepository(s)
        run = await repo.persist(prospect_id, job_id, outcome)
        return {
            "research_run_id": run.id,
            "status": outcome.status.value,
            "cached": False,
            "website_status": outcome.website_status,
            "evidence_count": len(outcome.evidence),
            "signals": outcome.signals,
            "sources_used": outcome.sources_used,
        }
