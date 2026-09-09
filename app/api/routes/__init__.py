from fastapi import APIRouter

from app.api.routes import (
    dashboard,
    discovery,
    evaluation,
    health,
    jobs,
    outreach,
    prospects,
    research,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
api_router.include_router(discovery.router, prefix="/api/v1/discovery", tags=["discovery"])
api_router.include_router(jobs.router, prefix="/api/v1/jobs", tags=["jobs"])
api_router.include_router(prospects.router, prefix="/api/v1/prospects", tags=["prospects"])
api_router.include_router(research.router, prefix="/api/v1/prospects", tags=["research"])
api_router.include_router(evaluation.router, prefix="/api/v1/prospects", tags=["evaluation"])
api_router.include_router(outreach.router, prefix="/api/v1", tags=["outreach"])
