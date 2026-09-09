"""Cleaning: drop junk, flag uncertain records for review (never silently delete
something that *might* be a real business).
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from app.core.logging import get_logger
from app.discovery.base import BusinessCandidate
from app.discovery.normalizer import canonical_business_name

log = get_logger(__name__)

# Names that are clearly not a single business.
_NON_BUSINESS_PATTERNS = [
    re.compile(r"^\s*$"),
    re.compile(r"^(home|contact|about|blog|news|login|search)\b", re.I),
    re.compile(r"\b(top \d+|best \d+|\d+ best)\b", re.I),
    re.compile(r"^(list of|categor|directory)\b", re.I),
]
_MIN_NAME_LEN = 2


class CleaningResult(BaseModel):
    kept: list[BusinessCandidate]
    reviewed: list[BusinessCandidate]  # kept but flagged quality_status=REVIEW
    dropped: list[dict]  # {candidate_name, reason}

    @property
    def all_kept(self) -> list[BusinessCandidate]:
        return self.kept + self.reviewed


def clean_candidates(candidates: list[BusinessCandidate]) -> CleaningResult:
    kept: list[BusinessCandidate] = []
    reviewed: list[BusinessCandidate] = []
    dropped: list[dict] = []

    for c in candidates:
        name = (c.business_name or "").strip()
        reason = _hard_reject_reason(c, name)
        if reason:
            dropped.append({"candidate_name": name or "<empty>", "reason": reason})
            continue
        if _needs_review(c, name):
            reviewed.append(c)
        else:
            kept.append(c)

    log.info(
        "cleaning.completed",
        input=len(candidates),
        kept=len(kept),
        review=len(reviewed),
        dropped=len(dropped),
    )
    return CleaningResult(kept=kept, reviewed=reviewed, dropped=dropped)


def _hard_reject_reason(c: BusinessCandidate, name: str) -> str | None:
    if len(name) < _MIN_NAME_LEN:
        return "name_too_short"
    if not canonical_business_name(name):
        return "name_has_no_meaningful_tokens"
    for pat in _NON_BUSINESS_PATTERNS:
        if pat.search(name):
            return f"non_business_pattern:{pat.pattern[:30]}"
    # a candidate with no website, no phone, no address, no place id is unusable
    if not any([c.domain, c.phone, c.address, c.google_place_id]):
        return "no_contactable_or_locating_signal"
    return None


def _needs_review(c: BusinessCandidate, name: str) -> bool:
    # web-search-only hit with just a domain and a guessed name -> human review
    if c.google_place_id is None and c.address is None and c.phone is None:
        return True
    return len(name) > 120
