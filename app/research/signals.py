"""Derive objective, conservative signals from parsed page(s) + business data.

Every signal is a fact ("no <X> element was found on the pages researched"),
never a judgement ("the website is bad"). Interpretation is the LLM's job later.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.research.http_client import FetchResult
from app.research.parser import ParsedPage


@dataclass
class WebsiteSignals:
    exists: bool = False
    reachable: bool = False
    status: str = "UNKNOWN"
    final_url: str | None = None
    is_https: bool | None = None
    has_title: bool | None = None
    has_meta_description: bool | None = None
    has_viewport_meta: bool | None = None
    pages_analyzed: int = 0
    total_text_length: int = 0
    has_contact_email: bool | None = None
    has_contact_phone: bool | None = None
    has_contact_form: bool | None = None
    has_booking_mechanism: bool | None = None
    has_online_ordering: bool | None = None
    has_live_chat: bool | None = None
    has_primary_cta: bool | None = None
    cta_texts: list[str] = field(default_factory=list)
    service_pages_found: list[str] = field(default_factory=list)
    has_faq_section: bool | None = None
    social_profiles: dict[str, str] = field(default_factory=dict)
    technology_signals: list[str] = field(default_factory=list)
    render_required: bool = False


@dataclass
class BusinessSignals:
    rating: float | None = None
    review_count: int | None = None
    category: str | None = None
    has_public_phone: bool = False
    has_public_email: bool = False
    has_website: bool = False
    contact_channels: list[str] = field(default_factory=list)


@dataclass
class ResearchSignals:
    website: WebsiteSignals
    business: BusinessSignals
    online_presence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "website": asdict(self.website),
            "business": asdict(self.business),
            "online_presence": self.online_presence,
        }


_SERVICE_HINTS = ("service", "treatment", "procedure", "what we do", "our work", "solutions")
_FAQ_HINTS = ("faq", "frequently asked", "questions")


def build_signals(
    *,
    prospect: dict,
    fetch: FetchResult | None,
    pages: list[ParsedPage],
) -> ResearchSignals:
    ws = WebsiteSignals()
    if fetch is not None:
        ws.status = fetch.status.value
        ws.final_url = fetch.final_url
        ws.reachable = fetch.usable_html
        ws.exists = bool(prospect.get("website")) or fetch.usable_html
        ws.render_required = any(p.text_length < 300 for p in pages) and bool(pages)

    if pages:
        primary = pages[0]
        ws.is_https = primary.is_https
        ws.has_title = bool(primary.title)
        ws.has_meta_description = bool(primary.meta_description)
        ws.has_viewport_meta = primary.has_viewport_meta
        ws.pages_analyzed = len(pages)
        ws.total_text_length = sum(p.text_length for p in pages)

        emails = {e for p in pages for e in p.emails}
        phones = {ph for p in pages for ph in p.phones}
        ws.has_contact_email = bool(emails)
        ws.has_contact_phone = bool(phones)
        ws.has_contact_form = any(p.has_forms for p in pages)
        ws.has_booking_mechanism = any(p.has_booking_link for p in pages)
        ws.has_online_ordering = any(p.has_online_ordering for p in pages)
        ws.has_live_chat = any(p.has_live_chat_widget for p in pages)
        cta = sorted({c for p in pages for c in p.cta_texts})
        ws.cta_texts = cta
        ws.has_primary_cta = bool(cta)

        nav_blob = " ".join(lbl.lower() for p in pages for lbl in p.nav_labels)
        head_blob = " ".join(h.lower() for p in pages for h in (p.headings + p.h1))
        blob = nav_blob + " " + head_blob
        ws.service_pages_found = [h for h in _SERVICE_HINTS if h in blob]
        ws.has_faq_section = any(h in blob for h in _FAQ_HINTS)

        social: dict[str, str] = {}
        for p in pages:
            social.update(p.social_profiles)
        ws.social_profiles = social
        ws.technology_signals = sorted({t for p in pages for t in p.tech_signals})

    bs = BusinessSignals(
        rating=prospect.get("rating"),
        review_count=prospect.get("review_count"),
        category=(prospect.get("provider_metadata") or {}).get("category"),
        has_public_phone=bool(prospect.get("phone")),
        has_public_email=bool(prospect.get("email")),
        has_website=bool(prospect.get("website")),
    )
    channels = []
    if bs.has_public_phone:
        channels.append("phone")
    if bs.has_public_email:
        channels.append("email")
    if ws.social_profiles.get("whatsapp"):
        channels.append("whatsapp")
    bs.contact_channels = channels

    online = {
        "has_website": bs.has_website,
        "social_platforms": sorted(ws.social_profiles.keys()),
        "website_status": ws.status,
    }
    return ResearchSignals(website=ws, business=bs, online_presence=online)
