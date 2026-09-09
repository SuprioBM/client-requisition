"""DuckDuckGo web search — SECONDARY discovery (website discovery, coverage top-up).

Uses the `ddgs` package (synchronous) off the event loop. Produces candidates
with a website/domain and a name guess; does not fabricate phone/address.
"""

from __future__ import annotations

import asyncio
import re

from app.core.errors import ErrorCode
from app.core.logging import get_logger
from app.db.models.enums import ProviderName
from app.discovery.base import BusinessCandidate, BusinessDiscoveryProvider, ProviderRun
from app.discovery.normalizer import canonical_domain, normalize_website

log = get_logger(__name__)

_DIRECTORY_DOMAINS = {
    "facebook.com", "instagram.com", "linkedin.com", "youtube.com", "twitter.com",
    "x.com", "yelp.com", "tripadvisor.com", "google.com", "maps.google.com",
    "wikipedia.org", "yellowpages.com", "justdial.com", "foursquare.com",
    "bing.com", "pinterest.com", "reddit.com",
}
_TITLE_SPLIT = re.compile(r"\s[-–—|:]\s")


class DuckDuckGoProvider(BusinessDiscoveryProvider):
    name = ProviderName.DUCKDUCKGO

    async def available(self) -> bool:
        return True  # no API key

    async def search(
        self,
        query: str,
        *,
        city: str,
        country: str,
        latitude: float | None = None,
        longitude: float | None = None,
        radius_km: float = 10.0,
        limit: int = 40,
    ) -> ProviderRun:
        run = ProviderRun(provider=self.name, query=query)
        full_query = f"{query} {city} {country}"
        timer = self.timer()
        with timer:
            try:
                rows = await asyncio.to_thread(self._text_search, full_query, limit)
                run.pages_requested = 1
                run.pages_received = 1
            except Exception as exc:  # noqa: BLE001 - ddgs raises many ad-hoc types
                run.status = "failed"
                run.error_code = _classify(exc)
                run.error_message = f"{type(exc).__name__}: {exc}"
                rows = []
        run.duration_ms = timer.ms

        seen: set[str] = set()
        for row in rows:
            href = row.get("href") or row.get("url")
            website = normalize_website(href)
            domain = canonical_domain(href)
            if not domain or domain in _DIRECTORY_DOMAINS or domain in seen:
                continue
            seen.add(domain)
            title = (row.get("title") or "").strip()
            name = _TITLE_SPLIT.split(title)[0].strip() or domain
            run.candidates.append(
                BusinessCandidate(
                    business_name=name,
                    website=website,
                    domain=domain,
                    city=city,
                    country=country,
                    provider=ProviderName.DUCKDUCKGO,
                    source_url=href,
                    search_query=query,
                    raw=row,
                )
            )
        run.result_count = len(run.candidates)
        if run.candidates and run.status == "failed":
            run.status = "partial"
        _log(run)
        return run

    @staticmethod
    def _text_search(query: str, limit: int) -> list[dict]:
        from ddgs import DDGS

        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=limit))


def _classify(exc: Exception) -> str:
    msg = str(exc).lower()
    if "rate" in msg or "429" in msg or "202" in msg:
        return ErrorCode.PROVIDER_RATE_LIMITED.value
    if "timeout" in msg:
        return ErrorCode.PROVIDER_TIMEOUT.value
    return ErrorCode.PROVIDER_UNAVAILABLE.value


def _log(run: ProviderRun) -> None:
    if run.ok:
        log.info(
            "duckduckgo.discovery.completed",
            query=run.query,
            results=run.result_count,
            duration_ms=run.duration_ms,
        )
    else:
        log.error(
            "duckduckgo.discovery.failed",
            query=run.query,
            error_code=run.error_code,
            reason=run.error_message,
        )
