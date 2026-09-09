from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import db_session, require_api_key
from app.core.errors import ErrorCode
from app.core.exceptions import NotFoundError
from app.db.models.enums import OutreachEventType
from app.db.models.outreach import OutreachMessage
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


class SaveDraftBody(BaseModel):
    actor: str = "operator"
    subject: str | None = None
    body: str | None = None


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


@router.get("/outreach")
async def list_all_outreach(
    session: AsyncSession = Depends(db_session),
    status: str | None = None,
    channel: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    stmt = select(OutreachMessage).options(selectinload(OutreachMessage.events))
    if status:
        stmt = stmt.where(OutreachMessage.status == status)
    if channel:
        stmt = stmt.where(OutreachMessage.channel == channel)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(OutreachMessage.created_at.desc()).limit(limit).offset(offset)
    rows = list((await session.execute(stmt)).scalars())

    # enrich with business name + score
    prospect_ids = {m.prospect_id for m in rows}
    names: dict[str, tuple[str, int | None]] = {}
    if prospect_ids:
        for p in (
            await session.execute(select(Prospect).where(Prospect.id.in_(prospect_ids)))
        ).scalars():
            names[p.id] = (p.business_name, None)

    items = []
    for m in rows:
        payload = _msg_payload(m)
        payload["business_name"] = names.get(m.prospect_id, ("(unknown)", None))[0]
        items.append(payload)
    return ok({"items": items, "total": int(total), "limit": limit, "offset": offset})


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


@router.patch("/outreach/{message_id}", dependencies=[Depends(require_api_key)])
async def save_outreach_draft(
    message_id: str, body: SaveDraftBody, session: AsyncSession = Depends(db_session)
) -> dict:
    repo = OutreachRepository(session)
    msg = await repo.get(message_id)
    if msg is None:
        raise NotFoundError("Outreach message not found", code=ErrorCode.NOT_FOUND)
    if msg.status not in ("PENDING_APPROVAL", "DRAFTED"):
        from app.core.exceptions import OutreachError

        raise OutreachError(
            f"Message is {msg.status}; cannot edit", code=ErrorCode.OUTREACH_NOT_APPROVED,
            http_status=409,
        )
    if body.subject is not None:
        msg.subject = body.subject
    if body.body is not None and body.body != msg.body:
        msg.edited_body = body.body
    await repo._event(msg.id, OutreachEventType.EDITED, {"by": body.actor})  # noqa: SLF001
    await session.commit()
    refreshed = await repo.get(message_id)
    return ok(_msg_payload(refreshed))


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
