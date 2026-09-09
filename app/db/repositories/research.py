from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.db.models.enums import ProspectStatus, ResearchRunStatus
from app.db.models.prospect import Prospect
from app.db.models.research import Evidence, ResearchRun
from app.research.orchestrator import ResearchOutcome

log = get_logger(__name__)


class ResearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def latest_run(self, prospect_id: str) -> ResearchRun | None:
        stmt = (
            select(ResearchRun)
            .where(ResearchRun.prospect_id == prospect_id)
            .order_by(desc(ResearchRun.created_at))
            .options(selectinload(ResearchRun.evidence))
            .limit(1)
        )
        return (await self.s.execute(stmt)).scalars().first()

    async def fresh_run(self, prospect_id: str, ttl_seconds: int) -> ResearchRun | None:
        run = await self.latest_run(prospect_id)
        if run is None or run.completed_at is None:
            return None
        if run.status not in (ResearchRunStatus.COMPLETED.value, ResearchRunStatus.PARTIAL.value):
            return None
        age = datetime.now(UTC) - run.completed_at.replace(tzinfo=UTC)
        return run if age < timedelta(seconds=ttl_seconds) else None

    async def persist(
        self, prospect_id: str, job_id: str | None, outcome: ResearchOutcome
    ) -> ResearchRun:
        now = datetime.now(UTC)
        run = ResearchRun(
            prospect_id=prospect_id,
            job_id=job_id,
            schema_version="v1",
            status=outcome.status.value,
            started_at=now,
            completed_at=now,
            sources_used=outcome.sources_used,
            website_status=outcome.website_status,
            website_final_url=outcome.website_final_url,
            signals=outcome.signals,
            social_profiles=outcome.social_profiles,
            content_hash=outcome.content_hash,
            error_code=outcome.error_code,
            error_message=outcome.error_message,
        )
        self.s.add(run)
        await self.s.flush()

        for ev in outcome.evidence:
            self.s.add(
                Evidence(
                    research_run_id=run.id,
                    prospect_id=prospect_id,
                    evidence_type=ev["evidence_type"],
                    source_type=ev["source_type"],
                    source_url=ev.get("source_url"),
                    extracted_text=ev.get("extracted_text"),
                    observation=ev["observation"],
                    confidence=ev["confidence"],
                    data_origin=ev.get("data_origin", "VERIFIED"),
                    extra=ev.get("extra", {}),
                    collected_at=now,
                )
            )

        prospect = await self.s.get(Prospect, prospect_id)
        if prospect is not None:
            prospect.last_researched_at = now
            if not prospect.website and outcome.discovered_website:
                prospect.website = outcome.discovered_website
            if prospect.status == ProspectStatus.DISCOVERED.value:
                prospect.status = ProspectStatus.RESEARCHED.value
        await self.s.flush()
        log.info("research.persisted", prospect_id=prospect_id, run_id=run.id,
                 evidence=len(outcome.evidence))
        return run

    async def evidence_for_run(self, run_id: str) -> list[Evidence]:
        stmt = select(Evidence).where(Evidence.research_run_id == run_id)
        return list((await self.s.execute(stmt)).scalars())
