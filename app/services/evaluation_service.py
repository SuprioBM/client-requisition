"""Full evaluation for one prospect: research -> pain points -> solutions ->
opportunity -> score -> outreach strategy -> email + WhatsApp drafts (PENDING_APPROVAL).
"""

from __future__ import annotations

import os
from typing import Any

from app.core.errors import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.logging import bind_contextvars, get_logger
from app.db.models.enums import OutreachChannel, OutreachStatus, ProspectStatus
from app.db.models.evaluation import EvaluationRun
from app.db.models.prospect import Prospect
from app.db.models.research import Evidence
from app.db.repositories.evaluation import EvaluationRepository
from app.db.repositories.outreach import OutreachRepository
from app.db.repositories.research import ResearchRepository
from app.db.session import session_scope
from app.evaluation import steps
from app.evaluation.llm import get_llm
from app.evaluation.prompts import PROMPT_VERSION, SCORING_VERSION
from app.evaluation.scoring import compute_score
from app.services.research_service import run_research

log = get_logger(__name__)

SENDER_NAME = os.environ.get("OUTREACH_SENDER_NAME", "Suprio")


def _prospect_dict(p: Prospect) -> dict[str, Any]:
    return {
        "id": p.id, "business_name": p.business_name, "industry": p.industry,
        "city": p.city, "country": p.country, "website": p.website,
        "phone": p.phone, "email": p.email, "rating": p.rating,
        "review_count": p.review_count, "provider_metadata": p.provider_metadata or {},
    }


def _evidence_dict(e: Evidence) -> dict[str, Any]:
    return {
        "id": e.id, "evidence_type": e.evidence_type, "source_type": e.source_type,
        "source_url": e.source_url, "observation": e.observation,
        "confidence": e.confidence, "data_origin": e.data_origin,
    }


async def run_evaluation(
    prospect_id: str, *, job_id: str | None = None, force_research: bool = False,
    generate_outreach: bool = True,
) -> dict[str, Any]:
    bind_contextvars(prospect_id=prospect_id, stage="evaluation")

    # 1. research (uses cache unless forced)
    research = await run_research(prospect_id, job_id=job_id, force=force_research)
    research_run_id = research["research_run_id"]

    async with session_scope() as s:
        prospect = await s.get(Prospect, prospect_id)
        if prospect is None:
            raise NotFoundError(f"Prospect {prospect_id} not found", code=ErrorCode.NOT_FOUND)
        pdict = _prospect_dict(prospect)
        if prospect.status in (ProspectStatus.DISCOVERED.value, ProspectStatus.RESEARCHED.value):
            prospect.status = ProspectStatus.EVALUATING.value

        rrepo = ResearchRepository(s)
        evidence_rows = await rrepo.evidence_for_run(research_run_id)
        evidence = [_evidence_dict(e) for e in evidence_rows]
        signals = research.get("signals", {}) or {}

        erepo = EvaluationRepository(s)
        run = await erepo.create_run(
            prospect_id, research_run_id=research_run_id, job_id=job_id,
            prompt_version=PROMPT_VERSION, scoring_version=SCORING_VERSION,
            model=get_llm().model_name,
        )
        run_id = run.id

    llm_meta: dict[str, Any] = {"calls": []}

    try:
        pp_list, m1 = await steps.detect_pain_points(pdict, signals, evidence)
        pain_points = [p.model_dump() for p in pp_list.pain_points]
        llm_meta["calls"].append(m1)

        sol_list, m2 = await steps.map_solutions(pdict, pain_points)
        solutions = sorted(
            (s.model_dump() for s in sol_list.solutions), key=lambda x: x.get("fit_rank", 99)
        )
        llm_meta["calls"].append(m2)

        opp, m3 = await steps.evaluate_opportunity(
            pdict, signals, pain_points, solutions, evidence
        )
        opportunity = opp.model_dump()
        llm_meta["calls"].append(m3)

        raw_score, m4 = await steps.propose_subscores(opportunity, pain_points, solutions, signals)
        llm_meta["calls"].append(m4)
        score = compute_score(
            raw_score, is_opportunity=opp.is_opportunity, evidence=evidence
        )
    except Exception as exc:
        async with session_scope() as s:
            failed = await s.get(EvaluationRun, run_id)
            if failed is not None:
                await EvaluationRepository(s).fail(
                    failed, ErrorCode.LLM_INVALID_OUTPUT.value, str(exc)
                )
        raise

    async with session_scope() as s:
        final_run = await s.get(EvaluationRun, run_id)
        assert final_run is not None
        await EvaluationRepository(s).finalize(
            final_run, opportunity=opportunity, score=score, pain_points=pain_points,
            solutions=solutions, llm_meta=llm_meta,
        )

    outreach_result: dict[str, Any] = {"generated": False}
    if generate_outreach and opp.is_opportunity and opp.outreach_worthwhile:
        outreach_result = await _generate_outreach(
            prospect_id, run_id, pdict, opportunity, pain_points, solutions, evidence, llm_meta
        )

    log.info("evaluation.run.completed", prospect_id=prospect_id, run_id=run_id,
             score=score["total"], is_opportunity=opp.is_opportunity,
             outreach=outreach_result.get("generated"))
    return {
        "evaluation_run_id": run_id,
        "research_run_id": research_run_id,
        "is_opportunity": opp.is_opportunity,
        "commercial_potential": opp.commercial_potential,
        "score": score,
        "pain_points": pain_points,
        "solutions": solutions,
        "opportunity": opportunity,
        "outreach": outreach_result,
    }


async def _generate_outreach(
    prospect_id: str, evaluation_run_id: str, pdict: dict, opportunity: dict,
    pain_points: list[dict], solutions: list[dict], evidence: list[dict], llm_meta: dict,
) -> dict[str, Any]:
    strategy_model, ms = await steps.generate_strategy(
        pdict, opportunity, pain_points, solutions, evidence
    )
    strategy = strategy_model.model_dump()
    llm_meta["calls"].append(ms)

    email_model, me = await steps.generate_email(pdict, strategy, SENDER_NAME)
    wa_model, mw = await steps.generate_whatsapp(pdict, strategy, SENDER_NAME)
    llm_meta["calls"] += [me, mw]

    created: list[dict] = []
    blocked: list[str] = []
    async with session_scope() as s:
        repo = OutreachRepository(s)
        prospect = await s.get(Prospect, prospect_id)

        specs = [
            (OutreachChannel.EMAIL, email_model.subject, email_model.body,
             prospect.email if prospect else None),
            (OutreachChannel.WHATSAPP, None, wa_model.body,
             prospect.phone if prospect else None),
        ]
        for channel, subject, body, to_addr in specs:
            existing = await repo.recent_message(prospect_id, channel)
            if existing is not None:
                blocked.append(channel.value)
                await repo._audit(  # noqa: SLF001
                    "outreach_message", existing.id, "duplicate blocked",
                    {"channel": channel.value},
                )
                continue
            msg = await repo.create(
                prospect_id=prospect_id,
                evaluation_run_id=evaluation_run_id,
                channel=channel,
                strategy=strategy,
                subject=subject,
                body=body,
                to_address=to_addr,
                prompt_version=PROMPT_VERSION,
                llm_meta={"strategy": ms, "draft": me if channel == OutreachChannel.EMAIL else mw},
                evidence_ids=strategy_model.evidence_ids,
                status=OutreachStatus.PENDING_APPROVAL,
            )
            created.append({"id": msg.id, "channel": channel.value, "status": msg.status})

        if prospect and created and prospect.status == ProspectStatus.EVALUATED.value:
            prospect.status = ProspectStatus.OUTREACH_DRAFTED.value

    return {
        "generated": bool(created),
        "messages": created,
        "blocked_duplicate": blocked,
        "strategy": strategy,
    }
