"""Deterministic discovery pipeline: location -> aggregate -> clean -> dedupe -> persist.

Phase 4 wraps these steps as LangGraph nodes; the logic lives here so it is
independently testable and reusable.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.core.logging import get_logger
from app.db.models.enums import RecordKind
from app.db.repositories.prospects import ProspectRepository
from app.db.session import session_scope
from app.discovery.aggregator import AggregationResult, run_discovery
from app.discovery.cleaner import CleaningResult, clean_candidates
from app.discovery.deduplicator import ProspectCluster, deduplicate
from app.discovery.location import ResolvedLocation, resolve_location

log = get_logger(__name__)


class DiscoverySummary(BaseModel):
    resolved_location: dict
    query_plan: dict
    provider_runs: list[dict]
    raw_candidates: int
    after_cleaning: int
    flagged_for_review: int
    dropped: int
    unique_clusters: int
    prospects_created: int
    prospects_updated: int
    prospect_ids: list[str]
    any_provider_succeeded: bool
    warnings: list[str]


async def resolve(city: str, country: str) -> ResolvedLocation:
    return await resolve_location(city, country)


async def aggregate(
    industry: str, location: ResolvedLocation, *, radius_km: float, target_leads: int
) -> AggregationResult:
    return await run_discovery(
        industry, location, radius_km=radius_km, target_leads=target_leads
    )


def clean(agg: AggregationResult) -> CleaningResult:
    return clean_candidates(agg.candidates)


def dedupe(cleaning: CleaningResult) -> list[ProspectCluster]:
    return deduplicate(cleaning.all_kept)


async def persist(
    clusters: list[ProspectCluster],
    review_candidate_ids: set[int],
    *,
    industry: str,
    country: str,
    city: str,
    job_id: str | None,
    record_kind: RecordKind = RecordKind.REAL,
) -> tuple[int, int, list[str]]:
    created_count = 0
    updated_count = 0
    ids: list[str] = []
    async with session_scope() as session:
        repo = ProspectRepository(session)
        for cluster in clusters:
            # a cluster needs review only if EVERY candidate in it was flagged
            needs_review = all(
                id(c) in review_candidate_ids for c in cluster.candidates
            )
            prospect, created = await repo.upsert_from_cluster(
                cluster,
                industry=industry,
                country=country,
                city=city,
                job_id=job_id,
                needs_review=needs_review,
                record_kind=record_kind,
            )
            ids.append(prospect.id)
            created_count += int(created)
            updated_count += int(not created)
    return created_count, updated_count, ids


async def run_discovery_pipeline(
    *,
    industry: str,
    city: str,
    country: str,
    radius_km: float = 10.0,
    target_leads: int = 60,
    job_id: str | None = None,
    record_kind: RecordKind = RecordKind.REAL,
) -> DiscoverySummary:
    warnings: list[str] = []

    location = await resolve(city, country)
    agg = await aggregate(
        industry, location, radius_km=radius_km, target_leads=target_leads
    )
    if not agg.any_success:
        # caller decides FAILED vs empty; report it
        warnings.append("all discovery providers failed")

    cleaning = clean(agg)
    review_ids = {id(c) for c in cleaning.reviewed}
    clusters = dedupe(cleaning)

    created, updated, ids = await persist(
        clusters,
        review_ids,
        industry=industry,
        country=country,
        city=city,
        job_id=job_id,
        record_kind=record_kind,
    )

    for run in agg.runs:
        if run.status == "failed":
            warnings.append(f"{run.provider.value} failed: {run.error_code}")

    summary = DiscoverySummary(
        resolved_location=location.model_dump(),
        query_plan=agg.query_plan,
        provider_runs=agg.provider_metadata(),
        raw_candidates=len(agg.candidates),
        after_cleaning=len(cleaning.all_kept),
        flagged_for_review=len(cleaning.reviewed),
        dropped=len(cleaning.dropped),
        unique_clusters=len(clusters),
        prospects_created=created,
        prospects_updated=updated,
        prospect_ids=ids,
        any_provider_succeeded=agg.any_success,
        warnings=warnings,
    )
    log.info(
        "discovery.pipeline.completed",
        created=created,
        updated=updated,
        unique=len(clusters),
        raw=len(agg.candidates),
        warnings=len(warnings),
    )
    return summary
