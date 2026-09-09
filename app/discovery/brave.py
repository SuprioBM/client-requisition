"""Brave Search API — SECONDARY discovery.

Web search endpoint. Requires BRAVE_SEARCH_API_KEY; skipped cleanly if absent.
"""

from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.core.errors import ErrorCode
from app.core.http import build_client, classify_http_error
from app.core.logging import get_logger
from app.db.models.enums import ProviderName
from app.discovery.base import BusinessCandidate, BusinessDiscoveryProvider, ProviderRun
from app.discovery.duckduckgo import _DIRECTORY_DOMAINS, _TITLE_SPLIT
from app.discovery.normalizer import canonical_domain, normalize_website

log = get_logger(__name__)

_URL = "https://api.search.brave.com/res/v1/web/search"


class BraveProvider(BusinessDiscoveryProvider):
    name = ProviderName.BRAVE

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or get_settings().brave_search_api_key

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
        limit: int = 20,
    ) -> ProviderRun:
        run = ProviderRun(provider=self.name, query=query)
        if not self._api_key:
            run.status = "skipped"
            run.error_code = ErrorCode.CONFIG_MISSING.value
            run.error_message = "BRAVE_SEARCH_API_KEY not configured"
            return run

        params: dict[str, str | int] = {"q": f"{query} {city} {country}", "count": min(limit, 20)}
        headers = {"X-Subscription-Token": self._api_key, "Accept": "application/json"}
        timer = self.timer()
        with timer:
            try:
                async with build_client(timeout=15.0) as client:
                    resp = await client.get(_URL, params=params, headers=headers)
                    resp.raise_for_status()
                    run.pages_requested = run.pages_received = 1
                    data = resp.json()
            except httpx.HTTPStatusError as exc:
                code, msg = classify_http_error(exc)
                run.status = "failed"
                run.error_code = code
                run.error_message = msg
                data = {}
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                code, msg = classify_http_error(exc)
                run.status = "failed"
                run.error_code = code
                run.error_message = msg
                data = {}
            except ValueError as exc:
                run.status = "failed"
                run.error_code = ErrorCode.PROVIDER_BAD_RESPONSE.value
                run.error_message = f"Malformed Brave response: {exc}"
                data = {}
        run.duration_ms = timer.ms

        seen: set[str] = set()
        for row in (data.get("web", {}) or {}).get("results", []) or []:
            href = row.get("url")
            domain = canonical_domain(href)
            if not domain or domain in _DIRECTORY_DOMAINS or domain in seen:
                continue
            seen.add(domain)
            title = (row.get("title") or "").strip()
            name = _TITLE_SPLIT.split(title)[0].strip() or domain
            run.candidates.append(
                BusinessCandidate(
                    business_name=name,
                    website=normalize_website(href),
                    domain=domain,
                    city=city,
                    country=country,
                    provider=ProviderName.BRAVE,
                    source_url=href,
                    search_query=query,
                    raw=row,
                )
            )
        run.result_count = len(run.candidates)
        if run.candidates and run.status == "failed":
            run.status = "partial"
        if run.ok:
            log.info(
                "brave.discovery.completed",
                query=run.query,
                results=run.result_count,
                duration_ms=run.duration_ms,
            )
        else:
            log.error(
                "brave.discovery.failed",
                query=run.query,
                error_code=run.error_code,
                reason=run.error_message,
            )
        return run
