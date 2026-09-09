"""Deterministic normalization of raw candidate fields.

Pure functions, no I/O. Used both by providers (to fill `domain`) and by the
aggregation pipeline (Phase 3).
"""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

import phonenumbers
import tldextract

_TLD = tldextract.TLDExtract(suffix_list_urls=())  # offline, no network

_LEGAL_SUFFIXES = {
    "ltd", "limited", "llc", "inc", "incorporated", "co", "company", "corp",
    "corporation", "plc", "gmbh", "pvt", "private", "pte", "llp", "sa", "srl",
    "bv", "ag", "kg", "oy", "ab",
}
_WS_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s&]")


def normalize_website(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    if not url:
        return None
    if not re.match(r"^https?://", url, re.I):
        url = "http://" + url
    try:
        p = urlparse(url)
    except ValueError:
        return None
    if not p.hostname:
        return None
    host = p.hostname.lower().lstrip(".")
    if host.startswith("www."):
        host = host[4:]
    scheme = "https" if p.scheme.lower() == "https" else "http"
    path = p.path.rstrip("/")
    return urlunparse((scheme, host, path, "", "", ""))


def canonical_domain(url: str | None) -> str | None:
    if not url:
        return None
    site = normalize_website(url)
    if not site:
        return None
    host = urlparse(site).hostname or ""
    ext = _TLD(host)
    if not ext.domain or not ext.suffix:
        return host or None
    return f"{ext.domain}.{ext.suffix}".lower()


def canonical_business_name(name: str) -> str:
    """Lowercased, punctuation-stripped, legal-suffix-stripped, whitespace-collapsed."""
    n = name.lower().strip()
    # drop trailing " - Location" style qualifiers only if separated by dash
    n = re.split(r"\s[-–—]\s", n)[0].strip() if " - " in name or " – " in name else n
    n = _NON_ALNUM_RE.sub(" ", n)
    tokens = [t for t in _WS_RE.sub(" ", n).split(" ") if t]
    while tokens and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens).strip()


def normalize_phone(raw: str | None, region: str | None = None) -> tuple[str | None, str | None]:
    """Return (display, e164). region is an ISO-3166 alpha-2 hint (e.g. 'BD')."""
    if not raw:
        return None, None
    raw = raw.strip()
    try:
        parsed = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException:
        return raw or None, None
    if not phonenumbers.is_possible_number(parsed):
        return raw or None, None
    e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    intl = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    return intl, e164


def normalize_address(addr: str | None) -> str | None:
    if not addr:
        return None
    a = _WS_RE.sub(" ", addr.replace("\n", ", ")).strip(" ,")
    a = re.sub(r"\s*,\s*", ", ", a)
    a = re.sub(r"(,\s*)+", ", ", a)
    return a or None


# ISO country-name -> alpha-2 for a handful of common cases; extended lazily.
_COUNTRY_ALPHA2 = {
    "bangladesh": "BD", "india": "IN", "pakistan": "PK", "united states": "US",
    "usa": "US", "united kingdom": "GB", "uk": "GB", "canada": "CA",
    "australia": "AU", "germany": "DE", "france": "FR", "singapore": "SG",
    "united arab emirates": "AE", "uae": "AE", "nepal": "NP", "sri lanka": "LK",
}


def country_to_region(country: str | None) -> str | None:
    if not country:
        return None
    return _COUNTRY_ALPHA2.get(country.strip().lower())
