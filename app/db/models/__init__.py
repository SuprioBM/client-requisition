"""Import every model so Alembic autogenerate and Base.metadata see them all."""

from app.db.base import Base
from app.db.models.evaluation import EvaluationRun, PainPoint, Solution
from app.db.models.job import Job
from app.db.models.outreach import AuditEvent, OutreachEvent, OutreachMessage
from app.db.models.prospect import Prospect, ProspectContact, ProspectSource
from app.db.models.research import Evidence, ResearchRun

__all__ = [
    "Base",
    "Job",
    "Prospect",
    "ProspectSource",
    "ProspectContact",
    "ResearchRun",
    "Evidence",
    "EvaluationRun",
    "PainPoint",
    "Solution",
    "OutreachMessage",
    "OutreachEvent",
    "AuditEvent",
]
