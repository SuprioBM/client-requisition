from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProspectSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    source_url: str | None = None
    search_query: str | None = None
    collected_at: datetime | None = None


class ProspectContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    channel: str
    value: str
    data_origin: str
    source_url: str | None = None
    verified: bool = False


class ProspectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_name: str
    normalized_name: str
    industry: str | None = None
    country: str | None = None
    city: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    phone: str | None = None
    phone_e164: str | None = None
    email: str | None = None
    website: str | None = None
    canonical_domain: str | None = None
    google_place_id: str | None = None
    rating: float | None = None
    review_count: int | None = None
    status: str
    quality_status: str
    record_kind: str
    last_researched_at: datetime | None = None
    last_evaluated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ProspectDetailOut(ProspectOut):
    sources: list[ProspectSourceOut] = []
    contacts: list[ProspectContactOut] = []
    provider_metadata: dict = {}
