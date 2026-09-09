from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import db_session, require_api_key
from app.core.errors import ErrorCode
from app.core.exceptions import NotFoundError
from app.db.models.prospect import Prospect
from app.db.repositories.outreach import OutreachRepository
from app.schemas.common import ok
from app.services import outreach_service
from app.services.evaluation_service import _generate_outreach  # reused helper

router = APIRouter()


class ApproveBody(BaseModel):
    actor: str = "operator"
    edited_body: str | None = None


class RejectBody(BaseModel):
    actor: str = "operator"
    reason: str | None = None


class SendBody(BaseModel):
    actor: str = "operator"
    override_duplicate: bool = False


def _msg_payload(m) -> dict:  # type: ignore[no-untyped-def]
    return {
        "id": m.id,
        "prospect_id": m.prospect_id,
        "channel": m.channel,
        "status": m.status,
        "subject": m.subject,
        "body": m.final_body,
        "to_address": m.to_address,
        "strategy": m.strategy,
        "evidence_ids": m.evidence_ids,
        "follow_up_count": m.follow_up_count,
        "next_follow_up_at": m.next_follow_up_at,
        "sent_at": m.sent_at,
        "events": [
            {"type": e.event_type, "detail": e.detail, "at": e.occurred_at} for e in m.events
        ],
        "created_at": m.created_at,
    }


@router.get("/prospects/{prospect_id}/outreach")
async def list_outreach(prospect_id: str, session: AsyncSession = Depends(db_session)) -> dict:
    msgs = await OutreachRepository(session).list_for_prospect(prospect_id)
    return ok([_msg_payload(m) for m in msgs])


@router.post(
    "/prospects/{prospect_id}/outreach/generate", dependencies=[Depends(require_api_key)]
)
async def generate_outreach(prospect_id: str, session: AsyncSession = Depends(db_session)) -> dict:
    from app.db.repositories.evaluation import EvaluationRepository
    from app.db.repositories.research import ResearchRepository

    prospect = await session.get(Prospect, prospect_id)
    if prospect is None:
        raise NotFoundError("Prospect not found", code=ErrorCode.NOT_FOUND)
    evaluation = await EvaluationRepository(session).latest(prospect_id)
    if evaluation is None:
        raise NotFoundError(
            "Evaluate the prospect before generating outreach", code=ErrorCode.NOT_FOUND
        )
    research = await ResearchRepository(session).latest_run(prospect_id)
    evidence = [
        {"id": e.id, "evidence_type": e.evidence_type, "source_type": e.source_type,
         "source_url": e.source_url, "observation": e.observation, "confidence": e.confidence,
         "data_origin": e.data_origin}
        for e in (research.evidence if research else [])
    ]
    pdict = {
        "id": prospect.id, "business_name": prospect.business_name, "industry": prospect.industry,
        "city": prospect.city, "country": prospect.country, "website": prospect.website,
        "phone": prospect.phone, "email": prospect.email,
    }
    opportunity = {
        "is_opportunity": evaluation.is_opportunity,
        "summary": evaluation.opportunity_summary,
        "reasoning": evaluation.opportunity_reasoning,
        "commercial_potential": evaluation.commercial_potential,
        "outreach_worthwhile": True,
    }
    pain_points = [
        {"category": pp.category, "title": pp.title, "description": pp.description,
         "confidence": pp.confidence, "evidence_ids": pp.evidence_ids}
        for pp in evaluation.pain_points
    ]
    solutions = [
        {"pain_point_title": "", "service_category": s.service_category,
         "service_name": s.service_name, "why_it_fits": s.why_it_fits,
         "expected_value": s.expected_value, "confidence": s.confidence, "fit_rank": s.fit_rank}
        for s in sorted(evaluation.solutions, key=lambda x: x.fit_rank)
    ]
    result = await _generate_outreach(
        prospect_id, evaluation.id, pdict, opportunity, pain_points, solutions, evidence,
        {"calls": []},
    )
    return ok(result)


@router.get("/outreach/{message_id}")
async def get_message(message_id: str, session: AsyncSession = Depends(db_session)) -> dict:
    msg = await OutreachRepository(session).get(message_id)
    if msg is None:
        raise NotFoundError("Outreach message not found", code=ErrorCode.NOT_FOUND)
    return ok(_msg_payload(msg))


@router.post("/outreach/{message_id}/approve", dependencies=[Depends(require_api_key)])
async def approve_message(message_id: str, body: ApproveBody) -> dict:
    return ok(await outreach_service.approve(message_id, actor=body.actor,
                                             edited_body=body.edited_body))


@router.post("/outreach/{message_id}/reject", dependencies=[Depends(require_api_key)])
async def reject_message(message_id: str, body: RejectBody) -> dict:
    return ok(await outreach_service.reject(message_id, actor=body.actor, reason=body.reason))


@router.post("/outreach/{message_id}/send", dependencies=[Depends(require_api_key)])
async def send_message(message_id: str, body: SendBody) -> dict:
    return ok(
        await outreach_service.send(
            message_id, actor=body.actor, override_duplicate=body.override_duplicate
        )
    )
