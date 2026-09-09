from __future__ import annotations

import pytest

from app.db.models.enums import ProviderName
from app.discovery.aggregator import run_discovery
from app.discovery.location import ResolvedLocation
from app.discovery.registry import set_provider_factory
from app.tests.mocks import MockDiscoveryProvider, make_candidate


@pytest.fixture
def location():
    return ResolvedLocation(
        query="Dhaka, Bangladesh",
        formatted_address="Dhaka, Bangladesh",
        city="Dhaka",
        country="Bangladesh",
        latitude=23.81,
        longitude=90.41,
        confidence=0.9,
        source="gazetteer",
    )


@pytest.fixture(autouse=True)
def _reset_factory():
    yield
    set_provider_factory(None)


async def test_aggregates_from_all_providers(location):
    g = MockDiscoveryProvider(ProviderName.GOOGLE_PLACES, [make_candidate("ABC Dental")])
    d = MockDiscoveryProvider(ProviderName.DUCKDUCKGO, [make_candidate("XYZ Dental")])
    set_provider_factory(lambda: [g, d])

    res = await run_discovery("dentist", location, target_leads=10)
    assert res.any_success
    names = {c.business_name for c in res.candidates}
    assert {"ABC Dental", "XYZ Dental"} <= names


async def test_partial_failure_is_not_fatal(location):
    g = MockDiscoveryProvider(ProviderName.GOOGLE_PLACES, fail_with="PROVIDER_QUOTA_EXCEEDED")
    d = MockDiscoveryProvider(ProviderName.DUCKDUCKGO, [make_candidate("XYZ Dental")])
    set_provider_factory(lambda: [g, d])

    res = await run_discovery("dentist", location, target_leads=10)
    assert res.any_success  # duckduckgo carried it
    meta = {m["provider"]: m for m in res.provider_metadata()}
    assert any(
        m["status"] == "failed" and m["error_code"] == "PROVIDER_QUOTA_EXCEEDED"
        for m in meta.values()
    )


async def test_all_providers_fail(location):
    g = MockDiscoveryProvider(ProviderName.GOOGLE_PLACES, fail_with="PROVIDER_UNAVAILABLE")
    d = MockDiscoveryProvider(ProviderName.DUCKDUCKGO, fail_with="PROVIDER_UNAVAILABLE")
    set_provider_factory(lambda: [g, d])

    res = await run_discovery("dentist", location, target_leads=10)
    assert not res.any_success
