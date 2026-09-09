"""Discovery provider contract + shared candidate model.

Business logic depends on `BusinessDiscoveryProvider`, never on a concrete
provider. Each provider returns a `ProviderRun` that always carries metadata
(provider, query, timing, status, error_code) so partial failures stay visible
and provider performance can be compared later.
"""

from __future__ import annotations

import abc
import time
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.db.models.enums import ProviderName


class BusinessCandidate(BaseModel):
    """One raw business hit from one provider. Provenance always retained."""

    business_name: str
    website: str | None = None
    domain: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    rating: float | None = None
    review_count: int | None = None
    category: str | None = None
    google_place_id: str | None = None

    # provenance
    provider: ProviderName
    source_url: str | None = None
    search_query: str | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw: dict = Field(default_factory=dict)

    def source_identity(self) -> str:
        """Stable key for this candidate *within its provider* (dedupe of provider pages)."""
        if self.google_place_id:
            return f"place:{self.google_place_id}"
        if self.domain:
            return f"domain:{self.domain}"
        if self.phone:
            return f"phone:{self.phone}"
        return f"name:{self.business_name.strip().lower()}|{(self.address or '').strip().lower()}"


class ProviderRun(BaseModel):
    provider: ProviderName
    query: str
    status: str = "ok"  # ok | partial | failed | skipped
    error_code: str | None = None
    error_message: str | None = None
    result_count: int = 0
    pages_requested: int = 0
    pages_received: int = 0
    duration_ms: int = 0
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    candidates: list[BusinessCandidate] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status in ("ok", "partial")


class _Timer:
    def __enter__(self) -> _Timer:
        self._t = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        self.ms = int((time.perf_counter() - self._t) * 1000)

    ms: int = 0


class BusinessDiscoveryProvider(abc.ABC):
    name: ProviderName

    @abc.abstractmethod
    async def available(self) -> bool:
        """Cheap check: is this provider configured/usable right now?"""

    @abc.abstractmethod
    async def search(
        self,
        query: str,
        *,
        city: str,
        country: str,
        latitude: float | None = None,
        longitude: float | None = None,
        radius_km: float = 10.0,
        limit: int = 60,
    ) -> ProviderRun:
        """Run one query. Must NOT raise for provider-side failures — return a
        ProviderRun with status='failed' and an error_code instead. May raise
        only for programmer error."""

    def timer(self) -> _Timer:
        return _Timer()
