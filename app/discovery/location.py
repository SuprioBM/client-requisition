"""Location resolution.

Order: Google Geocoding API (if key) -> offline gazetteer -> unresolved.
An unresolved / ambiguous location is a hard 400 at the API layer, never a
silent assumption.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.errors import ErrorCode
from app.core.exceptions import LocationError
from app.core.http import build_client
from app.core.logging import get_logger

log = get_logger(__name__)

_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

# Minimal offline fallback for common targets: (city, country) -> (lat, lng, country).
_GAZETTEER: dict[tuple[str, str], tuple[float, float, str]] = {
    ("dhaka", "bangladesh"): (23.8103, 90.4125, "Bangladesh"),
    ("chittagong", "bangladesh"): (22.3569, 91.7832, "Bangladesh"),
    ("chattogram", "bangladesh"): (22.3569, 91.7832, "Bangladesh"),
    ("sylhet", "bangladesh"): (24.8949, 91.8687, "Bangladesh"),
    ("london", "united kingdom"): (51.5072, -0.1276, "United Kingdom"),
    ("new york", "united states"): (40.7128, -74.0060, "United States"),
    ("san francisco", "united states"): (37.7749, -122.4194, "United States"),
    ("toronto", "canada"): (43.6532, -79.3832, "Canada"),
    ("sydney", "australia"): (-33.8688, 151.2093, "Australia"),
    ("singapore", "singapore"): (1.3521, 103.8198, "Singapore"),
    ("dubai", "united arab emirates"): (25.2048, 55.2708, "United Arab Emirates"),
    ("mumbai", "india"): (19.0760, 72.8777, "India"),
    ("delhi", "india"): (28.6139, 77.2090, "India"),
    ("bangalore", "india"): (12.9716, 77.5946, "India"),
    ("bengaluru", "india"): (12.9716, 77.5946, "India"),
}


class ResolvedLocation(BaseModel):
    query: str
    formatted_address: str
    city: str
    country: str
    latitude: float
    longitude: float
    confidence: float
    source: str  # google_geocoding | gazetteer


async def resolve_location(city: str, country: str) -> ResolvedLocation:
    city = (city or "").strip()
    country = (country or "").strip()
    if not city or not country:
        raise LocationError(
            "Both city and country are required to resolve a location",
            code=ErrorCode.LOCATION_INVALID,
            context={"city": city, "country": country},
        )

    settings = get_settings()
    if settings.google_maps_api_key:
        try:
            return await _google_geocode(city, country, settings.google_maps_api_key)
        except LocationError:
            raise
        except Exception as exc:  # noqa: BLE001 - fall through to gazetteer on infra error
            log.warning("location.google_geocode.failed", error=str(exc))

    key = (city.lower(), country.lower())
    if key in _GAZETTEER:
        lat, lng, canon_country = _GAZETTEER[key]
        log.info("location.resolved", city=city, country=canon_country, source="gazetteer")
        return ResolvedLocation(
            query=f"{city}, {country}",
            formatted_address=f"{city.title()}, {canon_country}",
            city=city.title(),
            country=canon_country,
            latitude=lat,
            longitude=lng,
            confidence=0.6,
            source="gazetteer",
        )

    raise LocationError(
        f"Could not resolve location {city!r}, {country!r}. "
        "Provide a Google Maps API key for geocoding or use a recognised city.",
        code=ErrorCode.LOCATION_UNRESOLVED,
        http_status=400,
        context={"city": city, "country": country},
    )


async def _google_geocode(city: str, country: str, api_key: str) -> ResolvedLocation:
    params = {"address": f"{city}, {country}", "key": api_key}
    async with build_client(timeout=12.0) as client:
        try:
            resp = await client.get(_GEOCODE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"geocoding transport error: {exc}") from exc

    status = data.get("status")
    results = data.get("results", []) or []

    if status == "REQUEST_DENIED":
        raise RuntimeError(f"geocoding request denied: {data.get('error_message')}")
    if status == "OVER_QUERY_LIMIT":
        raise RuntimeError("geocoding quota exceeded")
    if status == "ZERO_RESULTS" or (status == "OK" and not results):
        raise LocationError(
            f"No location found for {city!r}, {country!r}",
            code=ErrorCode.LOCATION_INVALID,
            http_status=400,
        )
    if status != "OK":
        raise RuntimeError(f"geocoding status {status}")

    # Ambiguity: multiple *distinct* localities returned.
    localities = {
        r["formatted_address"] for r in results if "locality" in r.get("types", [])
    } or {r["formatted_address"] for r in results}
    if len(localities) > 1:
        raise LocationError(
            f"Ambiguous location {city!r}, {country!r}: {sorted(localities)[:5]}",
            code=ErrorCode.LOCATION_AMBIGUOUS,
            http_status=400,
            context={"candidates": sorted(localities)[:5]},
        )

    top = results[0]
    loc = top["geometry"]["location"]
    comps = {t: c["long_name"] for c in top.get("address_components", []) for t in c["types"]}
    resolved = ResolvedLocation(
        query=f"{city}, {country}",
        formatted_address=top["formatted_address"],
        city=comps.get("locality") or comps.get("administrative_area_level_1") or city.title(),
        country=comps.get("country") or country.title(),
        latitude=loc["lat"],
        longitude=loc["lng"],
        confidence=0.95 if top.get("geometry", {}).get("location_type") == "APPROXIMATE" else 0.98,
        source="google_geocoding",
    )
    log.info(
        "location.resolved",
        city=resolved.city,
        country=resolved.country,
        source="google_geocoding",
    )
    return resolved
