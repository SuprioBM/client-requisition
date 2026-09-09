from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_api_key
from app.db.session import get_sessionmaker


async def db_session() -> AsyncIterator[AsyncSession]:
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


async def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Guard for mutating / outreach endpoints."""
    verify_api_key(x_api_key)


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


SessionDep = Depends(db_session)
ApiKeyDep = Depends(require_api_key)
