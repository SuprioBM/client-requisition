from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.db.models.enums import ProspectStatus
from app.db.models.evaluation import EvaluationRun, PainPoint, Solution
from app.db.models.prospect import Prospect

log = get_logger(__name__)


class EvaluationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def create_run(
        self, prospect_id: str, *, research_run_id: str | None, job_id: str | None,
        prompt_version: str, scoring_version: str, model: str | None,
    ) -> EvaluationRun:
        run = EvaluationRun(
            prospect_id=prospect_id,
            research_run_id=research_run_id,
            job_id=job_id,
            prompt_version=prompt_version,
            scoring_version=scoring_version,
            model=model,
            status="RUNNING",
        )
        self.s.add(run)
        await self.s.flush()
        return run

    async def finalize(
        self,
        run: EvaluationRun,
        *,
        opportunity: dict,
        score: dict,
        pain_points: list[dict],
        solutions: list[dict],
        llm_meta: dict,
        evidence_id_map: dict[str, str] | None = None,
    ) -> EvaluationRun:
        run.opportunity_summary = opportunity.get("summary")
        run.commercial_potential = opportunity.get("commercial_potential")
        run.opportunity_reasoning = opportunity.get("reasoning")
        run.is_opportunity = opportunity.get("is_opportunity")

        run.score_problem_severity = score.get("problem_severity")
        run.score_business_value = score.get("business_value")
        run.score_evidence_confidence = score.get("evidence_confidence")
        run.score_solution_fit = score.get("solution_fit")
        run.score_contactability = score.get("contactability")
        run.score_total = score.get("total")
        run.score_breakdown = score
        run.llm_meta = llm_meta
        run.status = "COMPLETED"
        run.completed_at = datetime.now(UTC)

        def _map(ids: list[str]) -> list[str]:
            if not evidence_id_map:
                return ids
            return [evidence_id_map.get(i, i) for i in ids]

        title_to_pp: dict[str, str] = {}
        for pp in pain_points:
            row = PainPoint(
                evaluation_run_id=run.id,
                prospect_id=run.prospect_id,
                category=pp["category"],
                title=pp["title"],
                description=pp["description"],
                confidence=pp["confidence"],
                evidence_ids=_map(pp.get("evidence_ids", [])),
            )
            self.s.add(row)
            await self.s.flush()
            title_to_pp[pp["title"]] = row.id

        for sol in solutions:
            self.s.add(
                Solution(
                    evaluation_run_id=run.id,
                    prospect_id=run.prospect_id,
                    pain_point_id=title_to_pp.get(sol.get("pain_point_title", "")),
                    service_category=sol["service_category"],
                    service_name=sol["service_name"],
                    why_it_fits=sol["why_it_fits"],
                    expected_value=sol["expected_value"],
                    confidence=sol["confidence"],
                    fit_rank=sol.get("fit_rank", 99),
                )
            )

        prospect = await self.s.get(Prospect, run.prospect_id)
        if prospect is not None:
            prospect.last_evaluated_at = datetime.now(UTC)
            if prospect.status in (
                ProspectStatus.DISCOVERED.value,
                ProspectStatus.RESEARCHED.value,
                ProspectStatus.EVALUATING.value,
            ):
                prospect.status = ProspectStatus.EVALUATED.value
        await self.s.flush()
        log.info("evaluation.finalized", prospect_id=run.prospect_id, run_id=run.id,
                 total=score.get("total"), pain_points=len(pain_points))
        return run

    async def fail(self, run: EvaluationRun, code: str, message: str) -> None:
        run.status = "FAILED"
        run.error_code = code
        run.error_message = message[:4000]
        run.completed_at = datetime.now(UTC)
        await self.s.flush()

    async def latest(self, prospect_id: str) -> EvaluationRun | None:
        stmt = (
            select(EvaluationRun)
            .where(EvaluationRun.prospect_id == prospect_id)
            .order_by(desc(EvaluationRun.created_at))
            .options(selectinload(EvaluationRun.pain_points), selectinload(EvaluationRun.solutions))
            .limit(1)
        )
        return (await self.s.execute(stmt)).scalars().first()
