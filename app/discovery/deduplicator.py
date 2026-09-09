"""Deduplication via union-find over multiple signals.

Strong signals (any match => same business):
  - google_place_id
  - canonical domain
  - phone (E.164)

Weak signals (combined => same business):
  - fuzzy(normalized name) >= 0.90 AND fuzzy(address) >= 0.80
  - fuzzy(normalized name) >= 0.95 AND same city AND no conflicting address

Branch protection: if two candidates share a domain/name but have addresses that
are clearly different locations (low address similarity AND both addresses
present), they are NOT merged.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from rapidfuzz import fuzz

from app.core.logging import get_logger
from app.discovery.base import BusinessCandidate
from app.discovery.normalizer import (
    canonical_business_name,
    normalize_address,
    normalize_phone,
)

log = get_logger(__name__)

_NAME_STRONG = 95.0
_NAME_WEAK = 90.0
_ADDR_MATCH = 80.0
_ADDR_CONFLICT = 45.0


class ProspectCluster(BaseModel):
    """A group of candidates believed to be the same business."""

    candidates: list[BusinessCandidate] = Field(default_factory=list)

    def merged(self) -> BusinessCandidate:
        """Deterministic field-by-field merge; Google/place data wins ties."""
        ordered = sorted(
            self.candidates,
            key=lambda c: (
                c.google_place_id is None,
                c.address is None,
                c.phone is None,
                c.provider.value,
            ),
        )
        base = ordered[0].model_copy(deep=True)
        for c in ordered[1:]:
            for field in (
                "website", "domain", "phone", "email", "address", "latitude",
                "longitude", "rating", "review_count", "category", "google_place_id",
            ):
                if getattr(base, field) in (None, "") and getattr(c, field) not in (None, ""):
                    setattr(base, field, getattr(c, field))
        return base

    def sources(self) -> list[BusinessCandidate]:
        return list(self.candidates)


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _addr_key(c: BusinessCandidate) -> str | None:
    return normalize_address(c.address)


def _phone_key(c: BusinessCandidate) -> str | None:
    _, e164 = normalize_phone(c.phone, None)
    return e164


def deduplicate(candidates: list[BusinessCandidate]) -> list[ProspectCluster]:
    n = len(candidates)
    uf = _UnionFind(n)

    norm_names = [canonical_business_name(c.business_name) for c in candidates]
    addrs = [_addr_key(c) for c in candidates]
    phones = [_phone_key(c) for c in candidates]
    domains = [c.domain for c in candidates]
    places = [c.google_place_id for c in candidates]

    # ---- strong-signal buckets ----
    for key_list in (places, domains, phones):
        buckets: dict[str, list[int]] = {}
        for i, k in enumerate(key_list):
            if k:
                buckets.setdefault(k, []).append(i)
        for idxs in buckets.values():
            for j in idxs[1:]:
                # domain match still respects branch protection
                if key_list is domains and _is_different_branch(
                    candidates[idxs[0]], candidates[j], addrs[idxs[0]], addrs[j]
                ):
                    continue
                uf.union(idxs[0], j)

    # ---- weak-signal pairwise (bounded: only within same first token) ----
    by_token: dict[str, list[int]] = {}
    for i, name in enumerate(norm_names):
        tok = name.split(" ")[0] if name else ""
        by_token.setdefault(tok, []).append(i)

    for idxs in by_token.values():
        for a_pos in range(len(idxs)):
            for b_pos in range(a_pos + 1, len(idxs)):
                i, j = idxs[a_pos], idxs[b_pos]
                if uf.find(i) == uf.find(j):
                    continue
                name_sort = fuzz.token_sort_ratio(norm_names[i], norm_names[j])
                name_set = fuzz.token_set_ratio(norm_names[i], norm_names[j])
                if name_set < _NAME_WEAK and name_sort < _NAME_WEAK:
                    continue
                if _is_different_branch(candidates[i], candidates[j], addrs[i], addrs[j]):
                    continue
                ai_addr, aj_addr = addrs[i], addrs[j]
                addr_sim = (
                    fuzz.token_sort_ratio(ai_addr, aj_addr)
                    if ai_addr and aj_addr
                    else None
                )
                same_city = (candidates[i].city or "").lower() == (candidates[j].city or "").lower()

                merge = False
                if name_set >= _NAME_WEAK and addr_sim is not None and addr_sim >= _ADDR_MATCH:
                    merge = True  # compatible name + same address
                elif name_sort >= _NAME_STRONG and addr_sim is None and same_city:
                    merge = True  # near-identical full name, same city, no address conflict
                elif addr_sim is not None and addr_sim >= 88 and name_set >= 70:
                    merge = True  # strong address match + plausibly same name

                if merge:
                    uf.union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(uf.find(i), []).append(i)

    clusters = [
        ProspectCluster(candidates=[candidates[i] for i in idxs]) for idxs in groups.values()
    ]
    log.info("deduplication.completed", input=n, unique=len(clusters))
    return clusters


def _is_different_branch(
    a: BusinessCandidate, b: BusinessCandidate, addr_a: str | None, addr_b: str | None
) -> bool:
    """True if these look like two physical branches of the same brand."""
    if addr_a and addr_b and fuzz.token_sort_ratio(addr_a, addr_b) < _ADDR_CONFLICT:
        return True
    # explicit branch qualifier in the raw name ("- Gulshan" vs "- Dhanmondi")
    qa = _branch_qualifier(a.business_name)
    qb = _branch_qualifier(b.business_name)
    if qa and qb and qa != qb:
        return True
    # different place ids => different locations
    return bool(
        a.google_place_id and b.google_place_id and a.google_place_id != b.google_place_id
    )


def _branch_qualifier(name: str) -> str | None:
    import re

    m = re.split(r"\s[-–—]\s", name)
    if len(m) > 1:
        return m[-1].strip().lower()
    return None
