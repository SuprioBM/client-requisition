from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import db_session
from app.core.errors import ErrorCode
from app.core.exceptions import NotFoundError
from app.db.models.prospect import Prospect
from app.schemas.common import ok
from app.schemas.prospect import ProspectDetailOut, ProspectOut

router = APIRouter()

_SORTS: dict[str, Any] = {
    "created_at": Prospect.created_at.desc(),
    "rating": Prospect.rating.desc(),
    "review_count": Prospect.review_count.desc(),
    "recently_researched": Prospect.last_researched_at.desc(),
}


@router.get("")
async def list_prospects(
    session: AsyncSession = Depends(db_session),
    industry: str | None = None,
    city: str | None = None,
    status: str | None = None,
    website_exists: bool | None = None,
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

    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    stmt = stmt.order_by(_SORTS.get(sort, Prospect.created_at.desc())).limit(limit).offset(offset)
    rows = list((await session.execute(stmt)).scalars())

    return ok(
        {
            "items": [ProspectOut.model_validate(r).model_dump() for r in rows],
            "total": int(total or 0),
            "limit": limit,
            "offset": offset,
        }
    )


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
