from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.db.models.enums import JobStatus, JobType


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_type: JobType
    status: JobStatus
    params: dict[str, Any]
    current_stage: str | None = None
    progress: dict[str, Any] = {}
    result: dict[str, Any] = {}
    warnings: list[Any] = []
    error_code: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    prospect_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class JobCreatedOut(BaseModel):
    job_id: str
    status: JobStatus
