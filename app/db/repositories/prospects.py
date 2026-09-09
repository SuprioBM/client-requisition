from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.db.models.enums import ProspectStatus, QualityStatus, RecordKind
from app.db.models.prospect import Prospect, ProspectContact, ProspectSource
from app.discovery.base import BusinessCandidate
from app.discovery.deduplicator import ProspectCluster
from app.discovery.normalizer import (
    canonical_business_name,
    country_to_region,
    normalize_phone,
)

log = get_logger(__name__)

_MERGEABLE_FIELDS = (
    "website", "canonical_domain", "phone", "email", "address", "latitude",
    "longitude", "rating", "review_count", "google_place_id",
)


class ProspectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def _match_existing(self, merged: BusinessCandidate, e164: str | None) -> Prospect | None:
        norm = canonical_business_name(merged.business_name)
        clauses = []
        if merged.google_place_id:
            clauses.append(Prospect.google_place_id == merged.google_place_id)
        if merged.domain:
            clauses.append(Prospect.canonical_domain == merged.domain)
        if e164:
            clauses.append(Prospect.phone_e164 == e164)
        if not clauses:
            # last resort: exact normalized name + city (avoids merging branches)
            stmt = select(Prospect).where(
                Prospect.normalized_name == norm,
                Prospect.city == merged.city,
                Prospect.address == merged.address,
            )
            return (await self.s.execute(stmt)).scalars().first()
        stmt = select(Prospect).where(or_(*clauses)).options(selectinload(Prospect.sources))
        return (await self.s.execute(stmt)).scalars().first()

    async def upsert_from_cluster(
        self,
        cluster: ProspectCluster,
        *,
        industry: str,
        country: str,
        city: str,
        job_id: str | None,
        needs_review: bool = False,
        record_kind: RecordKind = RecordKind.REAL,
    ) -> tuple[Prospect, bool]:
        merged = cluster.merged()
        region = country_to_region(country)
        display_phone, e164 = normalize_phone(merged.phone, region)

        existing = await self._match_existing(merged, e164)
        created = existing is None

        if created:
            prospect = Prospect(
                business_name=merged.business_name.strip(),
                normalized_name=canonical_business_name(merged.business_name),
                industry=industry,
                country=merged.country or country,
                city=merged.city or city,
                address=merged.address,
                latitude=merged.latitude,
                longitude=merged.longitude,
                phone=display_phone,
                phone_e164=e164,
                email=merged.email,
                website=merged.website,
                canonical_domain=merged.domain,
                google_place_id=merged.google_place_id,
                rating=merged.rating,
                review_count=merged.review_count,
                status=ProspectStatus.DISCOVERED.value,
                quality_status=(
                    QualityStatus.REVIEW.value if needs_review else QualityStatus.OK.value
                ),
                record_kind=record_kind.value,
                discovery_job_id=job_id,
                provider_metadata={"category": merged.category} if merged.category else {},
            )
            self.s.add(prospect)
            await self.s.flush()
        else:
            assert existing is not None
            prospect = existing
            # fill only missing fields; never overwrite existing verified data
            candidate_vals = {
                "website": merged.website,
                "canonical_domain": merged.domain,
                "phone": display_phone,
                "email": merged.email,
                "address": merged.address,
                "latitude": merged.latitude,
                "longitude": merged.longitude,
                "rating": merged.rating,
                "review_count": merged.review_count,
                "google_place_id": merged.google_place_id,
            }
            for field, val in candidate_vals.items():
                if getattr(prospect, field) in (None, "") and val not in (None, ""):
                    setattr(prospect, field, val)
            if prospect.phone_e164 is None and e164:
                prospect.phone_e164 = e164
            prospect.updated_at = datetime.now(UTC)

        await self._attach_sources(prospect, cluster.sources())
        await self._attach_contacts(prospect, merged, display_phone)
        await self.s.flush()
        return prospect, created

    async def _attach_sources(self, prospect: Prospect, candidates: list[BusinessCandidate]) -> None:
        existing_keys = {
            (src.provider, src.source_identity)
            for src in await self._load_sources(prospect.id)
        }
        for cand in candidates:
            key = (cand.provider.value, cand.source_identity())
            if key in existing_keys:
                continue
            existing_keys.add(key)
            self.s.add(
                ProspectSource(
                    prospect_id=prospect.id,
                    provider=cand.provider.value,
                    source_identity=cand.source_identity(),
                    source_url=cand.source_url,
                    search_query=cand.search_query,
                    raw_payload=cand.raw or {},
                    collected_at=cand.collected_at,
                )
            )

    async def _load_sources(self, prospect_id: str) -> list[ProspectSource]:
        stmt = select(ProspectSource).where(ProspectSource.prospect_id == prospect_id)
        return list((await self.s.execute(stmt)).scalars())

    async def _attach_contacts(
        self, prospect: Prospect, merged: BusinessCandidate, display_phone: str | None
    ) -> None:
        stmt = select(ProspectContact).where(ProspectContact.prospect_id == prospect.id)
        have = {(c.channel, c.value) for c in (await self.s.execute(stmt)).scalars()}
        wanted: list[tuple[str, str, str | None]] = []
        if display_phone:
            wanted.append(("phone", display_phone, None))
        if merged.email:
            wanted.append(("email", merged.email, merged.source_url))
        for channel, value, src in wanted:
            if (channel, value) in have:
                continue
            self.s.add(
                ProspectContact(
                    prospect_id=prospect.id,
                    channel=channel,
                    value=value,
                    data_origin="NORMALIZED" if channel == "phone" else "RAW",
                    source_url=src,
                )
            )

    async def get(self, prospect_id: str) -> Prospect | None:
        return await self.s.get(Prospect, prospect_id)
