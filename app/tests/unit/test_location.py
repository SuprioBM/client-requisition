from __future__ import annotations

import pytest

from app.core.exceptions import LocationError
from app.discovery.location import resolve_location


async def test_gazetteer_resolves_known_city():
    loc = await resolve_location("Dhaka", "Bangladesh")
    assert loc.source == "gazetteer"
    assert round(loc.latitude, 1) == 23.8
    assert loc.country == "Bangladesh"


async def test_missing_country_is_error():
    with pytest.raises(LocationError):
        await resolve_location("Dhaka", "")


async def test_unknown_city_is_400():
    with pytest.raises(LocationError) as ei:
        await resolve_location("Zzyzx Village", "Neverland")
    assert ei.value.http_status == 400


async def test_google_geocode_used_when_key_present(monkeypatch, respx_mock):
    import httpx

    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "google_maps_api_key", "fake", raising=False)
    respx_mock.get("https://maps.googleapis.com/maps/api/geocode/json").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "OK",
                "results": [
                    {
                        "formatted_address": "Paris, France",
                        "types": ["locality"],
                        "geometry": {"location": {"lat": 48.85, "lng": 2.35},
                                     "location_type": "APPROXIMATE"},
                        "address_components": [
                            {"long_name": "Paris", "types": ["locality"]},
                            {"long_name": "France", "types": ["country"]},
                        ],
                    }
                ],
            },
        )
    )
    loc = await resolve_location("Paris", "France")
    assert loc.source == "google_geocoding"
    assert loc.city == "Paris"


async def test_google_geocode_ambiguous(monkeypatch, respx_mock):
    import httpx

    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "google_maps_api_key", "fake", raising=False)
    respx_mock.get("https://maps.googleapis.com/maps/api/geocode/json").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "OK",
                "results": [
                    {"formatted_address": "Springfield, IL, USA", "types": ["locality"],
                     "geometry": {"location": {"lat": 1, "lng": 1}}, "address_components": []},
                    {"formatted_address": "Springfield, MO, USA", "types": ["locality"],
                     "geometry": {"location": {"lat": 2, "lng": 2}}, "address_components": []},
                ],
            },
        )
    )
    with pytest.raises(LocationError) as ei:
        await resolve_location("Springfield", "USA")
    assert ei.value.code.value == "LOCATION_AMBIGUOUS"
