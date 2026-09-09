"""Deterministic query planner: user input -> a small, diverse set of search queries.

No LLM. Uses a curated synonym map plus generic expansions, capped by
settings.max_queries_per_plan to control provider cost.
"""

from __future__ import annotations

from app.core.config import get_settings

# Curated expansions for common industries. Keys are matched case-insensitively
# as substrings of the user's industry term.
_INDUSTRY_SYNONYMS: dict[str, list[str]] = {
    "dentist": ["dentist", "dental clinic", "dental care", "orthodontist", "cosmetic dentist"],
    "dental": ["dental clinic", "dentist", "dental care", "orthodontist"],
    "restaurant": ["restaurant", "cafe", "diner", "eatery", "bistro"],
    "gym": ["gym", "fitness center", "health club", "crossfit box"],
    "salon": ["hair salon", "beauty salon", "barber shop", "nail salon"],
    "lawyer": ["law firm", "lawyer", "attorney", "legal services"],
    "clinic": ["medical clinic", "health clinic", "polyclinic", "diagnostic center"],
    "real estate": ["real estate agency", "property dealer", "realtor", "estate agent"],
    "hotel": ["hotel", "guest house", "boutique hotel", "resort"],
    "pharmacy": ["pharmacy", "drug store", "chemist", "medicine shop"],
    "accountant": ["accounting firm", "accountant", "bookkeeping service", "tax consultant"],
    "plumber": ["plumber", "plumbing service", "plumbing contractor"],
    "electrician": ["electrician", "electrical contractor", "electrical services"],
}

_GENERIC_SUFFIXES = ["", " services", " company", " near me"]


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        key = " ".join(it.lower().split())
        if key and key not in seen:
            seen.add(key)
            out.append(it.strip())
    return out


def expand_industry(industry: str) -> list[str]:
    term = industry.strip().lower()
    for key, syns in _INDUSTRY_SYNONYMS.items():
        if key in term:
            return list(syns)
    # fall back to light generic expansion
    base = industry.strip()
    return _dedupe_keep_order([base, f"{base} clinic", f"{base} company", f"{base} services"])


def plan_queries(industry: str, city: str, country: str) -> list[str]:
    settings = get_settings()
    cap = max(1, settings.max_queries_per_plan)
    variants = expand_industry(industry)
    queries = _dedupe_keep_order(variants)[:cap]
    return queries


def plan_web_search_queries(industry: str, city: str, country: str) -> list[str]:
    """Queries aimed at web search engines (need the location baked in)."""
    settings = get_settings()
    cap = max(1, settings.max_queries_per_plan)
    loc = f"{city} {country}".strip()
    out: list[str] = []
    for v in expand_industry(industry):
        out.append(f"{v} in {loc}")
    return _dedupe_keep_order(out)[:cap]
