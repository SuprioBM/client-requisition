"""Structural extraction from HTML via BeautifulSoup.

Deterministic. Produces objective structural facts only — no interpretation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.discovery.normalizer import canonical_domain

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(?:(?:\+|00)\d{1,3}[\s\-]?)?(?:\(?\d{2,4}\)?[\s\-]?){2,4}\d{2,4}")
_WS = re.compile(r"\s+")

_CTA_KEYWORDS = {
    "book now", "book online", "book appointment", "make appointment", "schedule",
    "request appointment", "get a quote", "request a quote", "order online",
    "buy now", "shop now", "contact us", "get started", "sign up", "subscribe",
    "call now", "whatsapp", "chat with us", "live chat",
}
_BOOKING_KEYWORDS = {"book", "appointment", "schedule", "reservation", "booking"}
_ORDER_KEYWORDS = {"order online", "order now", "add to cart", "checkout", "menu"}

_SOCIAL_HOSTS = {
    "facebook.com": "facebook",
    "instagram.com": "instagram",
    "linkedin.com": "linkedin",
    "youtube.com": "youtube",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "wa.me": "whatsapp",
    "api.whatsapp.com": "whatsapp",
    "t.me": "telegram",
    "tiktok.com": "tiktok",
}


@dataclass
class ParsedPage:
    url: str
    title: str | None = None
    meta_description: str | None = None
    lang: str | None = None
    h1: list[str] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)
    nav_labels: list[str] = field(default_factory=list)
    internal_links: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    social_profiles: dict[str, str] = field(default_factory=dict)
    has_forms: bool = False
    form_count: int = 0
    cta_texts: list[str] = field(default_factory=list)
    has_booking_link: bool = False
    has_online_ordering: bool = False
    has_live_chat_widget: bool = False
    has_viewport_meta: bool = False
    is_https: bool = False
    tech_signals: list[str] = field(default_factory=list)
    text_length: int = 0
    raw_link_count: int = 0


def _clean(s: str | None) -> str | None:
    if not s:
        return None
    s = _WS.sub(" ", s).strip()
    return s or None


def parse_html(html: str, url: str) -> ParsedPage:
    soup = BeautifulSoup(html, "lxml")
    page = ParsedPage(url=url)
    page.is_https = urlparse(url).scheme == "https"
    base_domain = canonical_domain(url)

    if soup.html and soup.html.get("lang"):
        page.lang = _clean(soup.html.get("lang"))
    if soup.title:
        page.title = _clean(soup.title.get_text())

    for m in soup.find_all("meta"):
        name = (m.get("name") or m.get("property") or "").lower()
        if name in ("description", "og:description") and not page.meta_description:
            page.meta_description = _clean(m.get("content"))
        if name == "viewport":
            page.has_viewport_meta = True
        if name == "generator" and m.get("content"):
            page.tech_signals.append(f"generator:{_clean(m.get('content'))}")

    page.h1 = [t for t in (_clean(h.get_text()) for h in soup.find_all("h1")) if t][:10]
    page.headings = [
        t for t in (_clean(h.get_text()) for h in soup.find_all(["h2", "h3"])) if t
    ][:40]

    nav = soup.find("nav") or soup.find(attrs={"role": "navigation"})
    if nav:
        page.nav_labels = [
            t for t in (_clean(a.get_text()) for a in nav.find_all("a")) if t
        ][:30]

    forms = soup.find_all("form")
    page.form_count = len(forms)
    page.has_forms = bool(forms)

    text_blob = soup.get_text(" ", strip=True)
    page.text_length = len(text_blob)
    lower_blob = text_blob.lower()

    page.emails = sorted(set(_EMAIL_RE.findall(text_blob)))[:10]
    # phones: check tel: links first (reliable), then loose text match
    tel_links = [
        a.get("href", "")[4:].strip()
        for a in soup.find_all("a", href=True)
        if a["href"].lower().startswith("tel:")
    ]
    page.phones = sorted({p for p in tel_links if p})[:10]

    links = soup.find_all("a", href=True)
    page.raw_link_count = len(links)
    internal: set[str] = set()
    for a in links:
        href = a["href"].strip()
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(url, href)
        host = (urlparse(absolute).hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        matched_social = next((v for k, v in _SOCIAL_HOSTS.items() if host.endswith(k)), None)
        if matched_social:
            page.social_profiles.setdefault(matched_social, absolute)
            continue
        if base_domain and canonical_domain(absolute) == base_domain:
            internal.add(absolute)
        label = (_clean(a.get_text()) or "").lower()
        if any(k in label for k in _BOOKING_KEYWORDS) or any(
            k in href.lower() for k in _BOOKING_KEYWORDS
        ):
            page.has_booking_link = True
        if any(k in label for k in _ORDER_KEYWORDS):
            page.has_online_ordering = True
    page.internal_links = sorted(internal)[:50]

    for kw in _CTA_KEYWORDS:
        if kw in lower_blob:
            page.cta_texts.append(kw)
    page.cta_texts = sorted(set(page.cta_texts))

    if any(k in lower_blob for k in ("order online", "add to cart", "checkout")):
        page.has_online_ordering = True

    # live chat / tech fingerprints (weak signals, stored as-is)
    html_lower = html.lower()
    for marker, sig in {
        "wp-content": "wordpress",
        "cdn.shopify.com": "shopify",
        "wixstatic.com": "wix",
        "squarespace.com": "squarespace",
        "_next/static": "nextjs",
        "react": "react",
        "tawk.to": "livechat:tawk",
        "widget.intercom.io": "livechat:intercom",
        "crisp.chat": "livechat:crisp",
        "wa.me/": "whatsapp_link",
    }.items():
        if marker in html_lower:
            page.tech_signals.append(sig)
            if sig.startswith("livechat"):
                page.has_live_chat_widget = True
    page.tech_signals = sorted(set(page.tech_signals))

    return page
