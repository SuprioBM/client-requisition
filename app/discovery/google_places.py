"""Google Places API (New) — Text Search. PRIMARY discovery provider.

Never raises for API-side failures: returns a ProviderRun with status='failed'
and a mapped error_code so the discovery job can continue on other providers.
"""

from __future__ import annotations

import asyncio

import httpx

from app.core.config import get_settings
from app.core.errors import ErrorCode
from app.core.http import build_client, classify_http_error
from app.core.logging import get_logger
from app.db.models.enums import ProviderName
from app.discovery.base import BusinessCandidate, BusinessDiscoveryProvider, ProviderRun
from app.discovery.normalizer import canonical_domain, normalize_website

log = get_logger(__name__)

_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
        "places.rating",
        "places.userRatingCount",
        "places.websiteUri",
        "places.internationalPhoneNumber",
        "places.nationalPhoneNumber",
        "places.primaryTypeDisplayName",
        "places.types",
        "nextPageToken",
    ]
)
_MAX_PAGES = 3  # API caps text search at 60 results (3 x 20)


class GooglePlacesProvider(BusinessDiscoveryProvider):
    name = ProviderName.GOOGLE_PLACES

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or get_settings().google_maps_api_key

    async def available(self) -> bool:
        return bool(self._api_key)

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
        run = ProviderRun(provider=self.name, query=query)
        if not self._api_key:
            run.status = "skipped"
            run.error_code = ErrorCode.CONFIG_MISSING.value
            run.error_message = "GOOGLE_MAPS_API_KEY not configured"
            return run

        text_query = f"{query} in {city}, {country}"
        body: dict = {"textQuery": text_query, "pageSize": 20}
        if latitude is not None and longitude is not None:
            body["locationBias"] = {
                "circle": {
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": min(radius_km, 50) * 1000,
                }
            }
        headers = {
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": _FIELD_MASK,
            "Content-Type": "application/json",
        }

        timer = self.timer()
        with timer:
            try:
                async with build_client(timeout=20.0) as client:
                    page_token: str | None = None
                    for _page in range(_MAX_PAGES):
                        if page_token:
                            body["pageToken"] = page_token
                            # Google requires a short delay before the next page token is valid
                            await asyncio.sleep(2)
                        resp = await client.post(_SEARCH_URL, json=body, headers=headers)
                        resp.raise_for_status()
                        run.pages_requested += 1
                        data = resp.json()
                        run.pages_received += 1
                        places = data.get("places", []) or []
                        for raw in places:
                            cand = self._to_candidate(raw, query, city, country)
                            if cand:
                                run.candidates.append(cand)
                        page_token = data.get("nextPageToken")
                        if not page_token or len(run.candidates) >= limit:
                            break
            except httpx.HTTPStatusError as exc:
                code, msg = classify_http_error(exc)
                # refine a few Google-specific signals from the body
                try:
                    err_body = exc.response.json().get("error", {})
                    status_txt = str(err_body.get("status", ""))
                    reason = str(err_body.get("message", ""))
                except Exception:  # noqa: BLE001
                    status_txt, reason = "", ""
                if "QUOTA" in status_txt or "RESOURCE_EXHAUSTED" in status_txt:
                    code = ErrorCode.PROVIDER_QUOTA_EXCEEDED.value
                if "billing" in reason.lower():
                    code = ErrorCode.PROVIDER_AUTH_FAILED.value
                run.status = "failed"
                run.error_code = code
                run.error_message = reason or msg
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                code, msg = classify_http_error(exc)
                run.status = "failed"
                run.error_code = code
                run.error_message = msg
            except (ValueError, KeyError) as exc:  # malformed JSON
                run.status = "failed"
                run.error_code = ErrorCode.PROVIDER_BAD_RESPONSE.value
                run.error_message = f"Malformed Google response: {exc}"

        run.duration_ms = timer.ms
        run.result_count = len(run.candidates)
        if run.candidates and run.status == "failed":
            run.status = "partial"
        _log_run(run)
        return run

    @staticmethod
    def _to_candidate(
        raw: dict, query: str, city: str, country: str
    ) -> BusinessCandidate | None:
        name = (raw.get("displayName") or {}).get("text")
        if not name:
            return None
        loc = raw.get("location") or {}
        website = raw.get("websiteUri")
        return BusinessCandidate(
            business_name=name,
            website=normalize_website(website),
            domain=canonical_domain(website),
            phone=raw.get("internationalPhoneNumber") or raw.get("nationalPhoneNumber"),
            address=raw.get("formattedAddress"),
            city=city,
            country=country,
            latitude=loc.get("latitude"),
            longitude=loc.get("longitude"),
            rating=raw.get("rating"),
            review_count=raw.get("userRatingCount"),
            category=(raw.get("primaryTypeDisplayName") or {}).get("text")
            or (raw.get("types") or [None])[0],
            google_place_id=raw.get("id"),
            provider=ProviderName.GOOGLE_PLACES,
            source_url=(
                f"https://www.google.com/maps/place/?q=place_id:{raw.get('id')}"
                if raw.get("id")
                else None
            ),
            search_query=query,
            raw=raw,
        )


def _log_run(run: ProviderRun) -> None:
    if run.ok:
        log.info(
            "google.discovery.completed",
            query=run.query,
            results=run.result_count,
            pages=run.pages_received,
            duration_ms=run.duration_ms,
            status=run.status,
        )
    else:
        log.error(
            "google.discovery.failed",
            query=run.query,
            error_code=run.error_code,
            reason=run.error_message,
            duration_ms=run.duration_ms,
        )
