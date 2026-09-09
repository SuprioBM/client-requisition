from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class DiscoverySearchRequest(BaseModel):
    country: str = Field(min_length=2, max_length=128)
    city: str = Field(min_length=1, max_length=128)
    industry: str = Field(min_length=2, max_length=128)
    radius_km: float = Field(default=10.0, gt=0, le=50)
    target_leads: int = Field(default=50, ge=1, le=500)

    # optional future-facing filters (accepted, applied best-effort)
    minimum_rating: float | None = Field(default=None, ge=0, le=5)
    minimum_reviews: int | None = Field(default=None, ge=0)
    website_required: bool = False
    contact_required: bool = False

    @field_validator("country", "city", "industry")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class QueryPlanOut(BaseModel):
    industry: str
    location_label: str
    queries: list[str]
    resolved_location: dict | None = None
