from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import db_session
from app.core.errors import ErrorCode
from app.core.exceptions import NotFoundError
from app.db.models.evaluation import EvaluationRun
from app.db.models.prospect import Prospect
from app.schemas.common import ok
from app.schemas.prospect import ProspectDetailOut, ProspectOut

router = APIRouter()

_SORTS: dict[str, Any] = {
    "created_at": Prospect.created_at.desc(),
    "rating": Prospect.rating.desc().nulls_last(),
    "review_count": Prospect.review_count.desc().nulls_last(),
    "recently_researched": Prospect.last_researched_at.desc().nulls_last(),
    "recently_evaluated": Prospect.last_evaluated_at.desc().nulls_last(),
}


async def _latest_scores(session: AsyncSession, prospect_ids: list[str]) -> dict[str, dict]:
    """Latest evaluation score + opportunity flag per prospect (single query)."""
    if not prospect_ids:
        return {}
    rn = func.row_number().over(
        partition_by=EvaluationRun.prospect_id,
        order_by=EvaluationRun.created_at.desc(),
    ).label("rn")
    sub = (
        select(
            EvaluationRun.prospect_id,
            EvaluationRun.score_total,
            EvaluationRun.is_opportunity,
            EvaluationRun.commercial_potential,
            rn,
        )
        .where(EvaluationRun.prospect_id.in_(prospect_ids))
        .subquery()
    )
    rows = await session.execute(select(sub).where(sub.c.rn == 1))
    return {
        r.prospect_id: {
            "score_total": r.score_total,
            "is_opportunity": r.is_opportunity,
            "commercial_potential": r.commercial_potential,
        }
        for r in rows
    }


@router.get("")
async def list_prospects(
    session: AsyncSession = Depends(db_session),
    industry: str | None = None,
    city: str | None = None,
    status: str | None = None,
    website_exists: bool | None = None,
    min_score: int | None = Query(None, ge=0, le=100),
    q: str | None = Query(None, description="search: name / domain / phone / city"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: str = Query("created_at"),
) -> dict:
    stmt = select(Prospect)
    if industry:
        stmt = stmt.where(Prospect.industry == industry)
    if city:
        stmt = stmt.where(Prospect.city == city)
    if status:
        stmt = stmt.where(Prospect.status == status)
    if website_exists is not None:
        stmt = stmt.where(
            Prospect.canonical_domain.is_not(None)
            if website_exists
            else Prospect.canonical_domain.is_(None)
        )
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            func.lower(Prospect.business_name).like(like)
            | func.lower(func.coalesce(Prospect.canonical_domain, "")).like(like)
            | func.lower(func.coalesce(Prospect.phone, "")).like(like)
            | func.lower(func.coalesce(Prospect.city, "")).like(like)
            | func.lower(func.coalesce(Prospect.industry, "")).like(like)
        )

    if sort == "score" or min_score is not None:
        # join latest score for filtering/sorting
        rn = func.row_number().over(
            partition_by=EvaluationRun.prospect_id, order_by=EvaluationRun.created_at.desc()
        ).label("rn")
        latest = (
            select(EvaluationRun.prospect_id, EvaluationRun.score_total, rn).subquery()
        )
        stmt = stmt.outerjoin(
            latest, (latest.c.prospect_id == Prospect.id) & (latest.c.rn == 1)
        )
        if min_score is not None:
            stmt = stmt.where(latest.c.score_total >= min_score)
        if sort == "score":
            stmt = stmt.order_by(latest.c.score_total.desc().nulls_last())

    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    if sort != "score":
        stmt = stmt.order_by(_SORTS.get(sort, Prospect.created_at.desc()))
    stmt = stmt.limit(limit).offset(offset)
    rows = list((await session.execute(stmt)).scalars())

    scores = await _latest_scores(session, [r.id for r in rows])
    items = []
    for r in rows:
        payload = ProspectOut.model_validate(r).model_dump()
        payload["evaluation"] = scores.get(r.id)
        items.append(payload)

    return ok({"items": items, "total": int(total or 0), "limit": limit, "offset": offset})


@router.get("/{prospect_id}")
async def get_prospect(prospect_id: str, session: AsyncSession = Depends(db_session)) -> dict:
    stmt = (
        select(Prospect)
        .where(Prospect.id == prospect_id)
        .options(selectinload(Prospect.sources), selectinload(Prospect.contacts))
    )
    prospect = (await session.execute(stmt)).scalar_one_or_none()
    if prospect is None:
        raise NotFoundError(f"Prospect {prospect_id} not found", code=ErrorCode.NOT_FOUND)
    return ok(ProspectDetailOut.model_validate(prospect).model_dump())
