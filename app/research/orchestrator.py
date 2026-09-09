"""Research pipeline for a single prospect.

    website known?
      yes -> HTTPX fetch
               usable HTML?  -> parse + extract  (+ up to 2 key internal pages)
               thin / JS?    -> Playwright render -> parse + extract
      no / failed -> DuckDuckGo + Brave search for the site / socials
                     still nothing important -> Tavily (if configured)
    -> deterministic signals -> Evidence list

Cost control: at most 3 HTTP page fetches, Playwright only when needed, Tavily
only as a last resort.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.db.models.enums import ProviderName, ResearchRunStatus, WebsiteStatus
from app.discovery.normalizer import canonical_domain, normalize_website
from app.discovery.registry import build_discovery_providers
from app.research import tavily
from app.research.evidence import build_evidence
from app.research.extractor import extract_main_text
from app.research.http_client import FetchResult, fetch
from app.research.parser import ParsedPage, parse_html
from app.research.playwright_client import looks_js_rendered, render
from app.research.signals import build_signals

log = get_logger(__name__)

_KEY_PAGE_HINTS = ("contact", "book", "appointment", "service", "about", "menu", "pricing")
_MAX_EXTRA_PAGES = 2


@dataclass
class ResearchOutcome:
    status: ResearchRunStatus
    website_status: str | None = None
    website_final_url: str | None = None
    signals: dict[str, Any] = field(default_factory=dict)
    social_profiles: dict[str, str] = field(default_factory=dict)
    content_hash: str | None = None
    sources_used: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    extracted_text: str | None = None
    discovered_website: str | None = None
    error_code: str | None = None
    error_message: str | None = None


def _hash(text: str | None) -> str | None:
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()


async def _fetch_and_parse(url: str) -> tuple[FetchResult, ParsedPage | None]:
    result = await fetch(url)
    page: ParsedPage | None = None
    if result.usable_html:
        page = parse_html(result.html or "", result.final_url or url)
        if looks_js_rendered(result.html, page.text_length):
            html, err = await render(result.final_url or url)
            if html:
                page = parse_html(html, result.final_url or url)
                result.html = html
    elif result.status in (WebsiteStatus.UNKNOWN, WebsiteStatus.TIMEOUT):
        html, err = await render(url)
        if html:
            result.status = WebsiteStatus.ACTIVE
            result.final_url = result.final_url or url
            result.html = html
            page = parse_html(html, result.final_url or url)
    return result, page


async def _discover_website(name: str, city: str, country: str) -> tuple[str | None, dict, list[str]]:
    """Use DDG + Brave to find a likely official website / socials."""
    providers = {p.name: p for p in build_discovery_providers()}
    used: list[str] = []
    query = f"{name} {city}"
    best_domain: str | None = None
    socials: dict[str, str] = {}
    for pname in (ProviderName.DUCKDUCKGO, ProviderName.BRAVE):
        provider = providers.get(pname)
        if provider is None or not await provider.available():
            continue
        used.append(pname.value)
        run = await provider.search(query, city=city, country=country, limit=8)
        for c in run.candidates:
            if c.domain and not best_domain:
                best_domain = c.domain
    return (f"https://{best_domain}" if best_domain else None), socials, used


async def research_prospect(prospect: dict) -> ResearchOutcome:
    name = prospect.get("business_name", "")
    city = prospect.get("city") or ""
    country = prospect.get("country") or ""
    website = normalize_website(prospect.get("website"))
    outcome = ResearchOutcome(status=ResearchRunStatus.RUNNING)
    pages: list[ParsedPage] = []
    fetch_result: FetchResult | None = None
    used: list[str] = []

    if website:
        used.append(ProviderName.DIRECT_HTTP.value)
        fetch_result, primary = await _fetch_and_parse(website)
        outcome.website_status = fetch_result.status.value
        outcome.website_final_url = fetch_result.final_url
        if primary:
            pages.append(primary)
            # follow up to 2 key internal pages
            extra = [
                u for u in primary.internal_links
                if any(h in u.lower() for h in _KEY_PAGE_HINTS)
            ][:_MAX_EXTRA_PAGES]
            for u in extra:
                _r, p = await _fetch_and_parse(u)
                if p:
                    pages.append(p)

    # fallback: no website, or site unreachable / thin
    need_fallback = not website or not pages or (pages and pages[0].text_length < 200)
    if need_fallback:
        discovered, socials, disc_used = await _discover_website(name, city, country)
        used.extend(disc_used)
        if discovered and canonical_domain(discovered) != canonical_domain(website or ""):
            outcome.discovered_website = discovered
            _r, p = await _fetch_and_parse(discovered)
            if p:
                pages.append(p)
                fetch_result = _r
                outcome.website_status = _r.status.value
                outcome.website_final_url = _r.final_url

    tavily_results: list[dict] = []
    still_thin = not pages or sum(p.text_length for p in pages) < 300
    if still_thin and tavily.available():
        used.append(ProviderName.TAVILY.value)
        tavily_results, terr = await tavily.search(f"{name} {city} {country} business")
        if terr:
            outcome.error_code = terr

    extracted = None
    if pages and fetch_result and fetch_result.html:
        extracted = extract_main_text(fetch_result.html, fetch_result.final_url or website or "")
    outcome.extracted_text = extracted

    signals = build_signals(prospect=prospect, fetch=fetch_result, pages=pages)
    outcome.signals = signals.to_dict()
    outcome.social_profiles = signals.website.social_profiles
    outcome.content_hash = _hash(extracted or (pages[0].title if pages else None))
    outcome.sources_used = sorted(set(used))
    outcome.evidence = build_evidence(
        prospect=prospect, signals=signals, extracted_text=extracted,
        tavily_results=tavily_results,
    )

    if pages:
        outcome.status = ResearchRunStatus.COMPLETED
    elif tavily_results or (fetch_result and fetch_result.status != WebsiteStatus.UNKNOWN):
        outcome.status = ResearchRunStatus.PARTIAL
    else:
        outcome.status = ResearchRunStatus.PARTIAL
        outcome.error_code = outcome.error_code or "WEBSITE_NOT_FOUND"

    log.info(
        "research.prospect.completed",
        prospect=name,
        status=outcome.status.value,
        pages=len(pages),
        evidence=len(outcome.evidence),
        sources=outcome.sources_used,
        website_status=outcome.website_status,
    )
    return outcome
