from __future__ import annotations

from fastapi import APIRouter

from app.core import redis as redis_mod
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import session as db
from app.schemas.common import ok

log = get_logger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return ok({"status": "ok"})


@router.get("/health/ready")
async def readiness() -> dict:
    settings = get_settings()
    checks: dict[str, str] = {}
    healthy = True

    try:
        await db.ping()
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc}"
        healthy = False

    try:
        await redis_mod.ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc}"
        healthy = False

    payload = {
        "healthy": healthy,
        "checks": checks,
        "capabilities": settings.capability_summary(),
        "env": settings.app_env.value,
    }
    return ok(payload) if healthy else {"success": False, "data": payload, "error": None}
