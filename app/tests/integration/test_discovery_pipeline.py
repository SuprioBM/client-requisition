from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.db.models.enums import ProviderName
from app.db.models.prospect import Prospect, ProspectSource
from app.discovery.registry import set_provider_factory
from app.services.discovery_service import run_discovery_pipeline
from app.tests.mocks import MockDiscoveryProvider, make_candidate


@pytest.fixture(autouse=True)
def _providers():
    google = MockDiscoveryProvider(
        ProviderName.GOOGLE_PLACES,
        [
            make_candidate(
                "ABC Dental Clinic", google_place_id="P1", domain="abcdental.com",
                phone="+8801712345678", address="12 Road 5, Dhanmondi, Dhaka", rating=4.6,
            ),
            make_candidate(
                "Smile Studio", google_place_id="P2", address="9 Gulshan Ave, Dhaka",
                phone="+8801811111111",
            ),
        ],
    )
    brave = MockDiscoveryProvider(
        ProviderName.BRAVE,
        [make_candidate("ABC Dental", domain="abcdental.com")],  # dupe of P1 by domain
    )
    set_provider_factory(lambda: [google, brave])
    yield
    set_provider_factory(None)


async def test_pipeline_persists_deduped_prospects(session):
    summary = await run_discovery_pipeline(
        industry="dentist", city="Dhaka", country="Bangladesh", target_leads=10
    )
    assert summary.any_provider_succeeded
    # mock providers echo their candidates for every planned query; dedup collapses them
    assert summary.unique_clusters == 2
    assert summary.prospects_created == 2

    total = await session.scalar(select(func.count()).select_from(Prospect))
    assert total == 2

    abc = (
        await session.execute(select(Prospect).where(Prospect.canonical_domain == "abcdental.com"))
    ).scalar_one()
    # both google + brave sources recorded
    srcs = (
        await session.execute(select(ProspectSource).where(ProspectSource.prospect_id == abc.id))
    ).scalars().all()
    assert {s.provider for s in srcs} == {"google_places", "brave"}
    assert abc.phone_e164 == "+8801712345678"


async def test_pipeline_is_idempotent(session):
    s1 = await run_discovery_pipeline(
        industry="dentist", city="Dhaka", country="Bangladesh", target_leads=10
    )
    s2 = await run_discovery_pipeline(
        industry="dentist", city="Dhaka", country="Bangladesh", target_leads=10
    )
    assert s1.prospects_created == 2
    assert s2.prospects_created == 0
    assert s2.prospects_updated == 2

    total = await session.scalar(select(func.count()).select_from(Prospect))
    assert total == 2
    # no duplicate sources on the re-run
    src_total = await session.scalar(select(func.count()).select_from(ProspectSource))
    assert src_total == 3
