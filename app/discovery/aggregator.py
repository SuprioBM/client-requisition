"""Run every available discovery provider, gather candidates + provenance.

- Google Places gets the plain industry queries (it handles location itself).
- DuckDuckGo / Brave get location-baked web-search queries.
- Bounded concurrency (settings.discovery_provider_concurrency).
- Partial provider failure is recorded, never fatal. All providers failing ->
  caller marks the job FAILED with discovery_providers_unavailable.
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.enums import ProviderName
from app.discovery.base import BusinessCandidate, ProviderRun
from app.discovery.location import ResolvedLocation
from app.discovery.planner import plan_queries, plan_web_search_queries
from app.discovery.registry import build_discovery_providers

log = get_logger(__name__)

_WEB_PROVIDERS = {ProviderName.DUCKDUCKGO, ProviderName.BRAVE}


class AggregationResult(BaseModel):
    candidates: list[BusinessCandidate] = Field(default_factory=list)
    runs: list[ProviderRun] = Field(default_factory=list)
    query_plan: dict = Field(default_factory=dict)

    @property
    def any_success(self) -> bool:
        return any(r.ok and r.status != "skipped" for r in self.runs)

    @property
    def attempted(self) -> list[ProviderRun]:
        return [r for r in self.runs if r.status != "skipped"]

    def provider_metadata(self) -> list[dict]:
        return [
            {
                "provider": r.provider.value,
                "query": r.query,
                "status": r.status,
                "error_code": r.error_code,
                "result_count": r.result_count,
                "duration_ms": r.duration_ms,
                "pages_received": r.pages_received,
                "started_at": r.started_at.isoformat(),
            }
            for r in self.runs
        ]


async def run_discovery(
    industry: str,
    location: ResolvedLocation,
    *,
    radius_km: float = 10.0,
    target_leads: int = 60,
) -> AggregationResult:
    settings = get_settings()
    providers = build_discovery_providers()

    place_queries = plan_queries(industry, location.city, location.country)
    web_queries = plan_web_search_queries(industry, location.city, location.country)
    result = AggregationResult(
        query_plan={"place_queries": place_queries, "web_queries": web_queries}
    )

    sem = asyncio.Semaphore(max(1, settings.discovery_provider_concurrency))

    async def _one(provider, query: str) -> ProviderRun:  # type: ignore[no-untyped-def]
        async with sem:
            try:
                if not await provider.available():
                    return ProviderRun(
                        provider=provider.name, query=query, status="skipped",
                        error_code="CONFIG_MISSING",
                    )
                return await provider.search(
                    query,
                    city=location.city,
                    country=location.country,
                    latitude=location.latitude,
                    longitude=location.longitude,
                    radius_km=radius_km,
                    limit=max(20, target_leads),
                )
            except Exception as exc:  # provider bug -> contained, logged, non-fatal
                log.error(
                    "discovery.provider.crashed",
                    provider=provider.name.value,
                    query=query,
                    error=str(exc),
                    exc_info=True,
                )
                return ProviderRun(
                    provider=provider.name, query=query, status="failed",
                    error_code="PROVIDER_BAD_RESPONSE", error_message=str(exc),
                )

    tasks: list = []
    for provider in providers:
        queries = web_queries if provider.name in _WEB_PROVIDERS else place_queries
        for q in queries:
            tasks.append(_one(provider, q))

    log.info(
        "discovery.aggregation.started",
        providers=[p.name.value for p in providers],
        place_queries=len(place_queries),
        web_queries=len(web_queries),
        tasks=len(tasks),
    )
    runs = await asyncio.gather(*tasks)
    result.runs = list(runs)
    for r in runs:
        result.candidates.extend(r.candidates)

    by_provider: dict[str, int] = {}
    for r in runs:
        by_provider[r.provider.value] = by_provider.get(r.provider.value, 0) + r.result_count
    log.info(
        "discovery.aggregation.completed",
        total_candidates=len(result.candidates),
        by_provider=by_provider,
        any_success=result.any_success,
    )
    return result
