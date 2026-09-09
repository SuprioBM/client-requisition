from __future__ import annotations

import httpx
import pytest

from app.discovery.brave import BraveProvider
from app.discovery.google_places import GooglePlacesProvider


@pytest.fixture
def google_body():
    return {
        "places": [
            {
                "id": "PLACE1",
                "displayName": {"text": "ABC Dental Clinic"},
                "formattedAddress": "12 Road 5, Dhanmondi, Dhaka",
                "location": {"latitude": 23.74, "longitude": 90.37},
                "rating": 4.6,
                "userRatingCount": 88,
                "websiteUri": "https://www.abcdental.com",
                "internationalPhoneNumber": "+880 1712-345678",
                "primaryTypeDisplayName": {"text": "Dentist"},
                "types": ["dentist"],
            }
        ]
    }


async def test_google_places_parses_results(respx_mock, google_body):
    respx_mock.post("https://places.googleapis.com/v1/places:searchText").mock(
        return_value=httpx.Response(200, json=google_body)
    )
    p = GooglePlacesProvider(api_key="fake")
    run = await p.search("dentist", city="Dhaka", country="Bangladesh")
    assert run.ok and run.result_count == 1
    c = run.candidates[0]
    assert c.google_place_id == "PLACE1"
    assert c.domain == "abcdental.com"
    assert c.rating == 4.6


async def test_google_places_missing_key_is_skipped():
    p = GooglePlacesProvider(api_key=None)
    run = await p.search("dentist", city="Dhaka", country="Bangladesh")
    assert run.status == "skipped"
    assert run.error_code == "CONFIG_MISSING"


async def test_google_places_quota_maps_to_error_code(respx_mock):
    respx_mock.post("https://places.googleapis.com/v1/places:searchText").mock(
        return_value=httpx.Response(
            429, json={"error": {"status": "RESOURCE_EXHAUSTED", "message": "quota"}}
        )
    )
    p = GooglePlacesProvider(api_key="fake")
    run = await p.search("dentist", city="Dhaka", country="Bangladesh")
    assert run.status == "failed"
    assert run.error_code == "PROVIDER_QUOTA_EXCEEDED"


async def test_google_places_auth_failure(respx_mock):
    respx_mock.post("https://places.googleapis.com/v1/places:searchText").mock(
        return_value=httpx.Response(403, json={"error": {"status": "PERMISSION_DENIED",
                                                          "message": "billing not enabled"}})
    )
    p = GooglePlacesProvider(api_key="fake")
    run = await p.search("dentist", city="Dhaka", country="Bangladesh")
    assert run.status == "failed"
    assert run.error_code == "PROVIDER_AUTH_FAILED"


async def test_google_places_timeout(respx_mock):
    respx_mock.post("https://places.googleapis.com/v1/places:searchText").mock(
        side_effect=httpx.ConnectTimeout("timed out")
    )
    p = GooglePlacesProvider(api_key="fake")
    run = await p.search("dentist", city="Dhaka", country="Bangladesh")
    assert run.status == "failed"
    assert run.error_code == "PROVIDER_TIMEOUT"


async def test_brave_parses_and_filters_directories(respx_mock):
    respx_mock.get("https://api.search.brave.com/res/v1/web/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {"title": "ABC Dental - Best in Dhaka", "url": "https://abcdental.com"},
                        {"title": "ABC Dental | Facebook", "url": "https://facebook.com/abc"},
                    ]
                }
            },
        )
    )
    p = BraveProvider(api_key="fake")
    run = await p.search("dentist", city="Dhaka", country="Bangladesh")
    assert run.result_count == 1
    assert run.candidates[0].domain == "abcdental.com"


async def test_brave_missing_key_skipped():
    run = await BraveProvider(api_key=None).search("x", city="Dhaka", country="Bangladesh")
    assert run.status == "skipped"
