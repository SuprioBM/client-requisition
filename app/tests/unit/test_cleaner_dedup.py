from __future__ import annotations

from app.discovery.cleaner import clean_candidates
from app.discovery.deduplicator import deduplicate
from app.tests.mocks import make_candidate


def test_cleaner_drops_junk_and_flags_review():
    cands = [
        make_candidate("ABC Dental", google_place_id="P1", address="12 Rd, Dhaka", phone="+8801711111111"),
        make_candidate(""),  # dropped
        make_candidate("Home"),  # dropped: non-business pattern
        make_candidate("Top 10 Dentists in Dhaka", domain="listicle.com"),  # dropped
        make_candidate("XYZ Dental", domain="xyzdental.com"),  # review: web-only
    ]
    res = clean_candidates(cands)
    kept_names = {c.business_name for c in res.kept}
    review_names = {c.business_name for c in res.reviewed}
    assert "ABC Dental" in kept_names
    assert "XYZ Dental" in review_names
    assert len(res.dropped) == 3


def test_dedup_strong_signal_domain_and_phone():
    cands = [
        make_candidate("ABC Dental", domain="abc.com", phone="+8801712345678"),
        make_candidate("ABC Dental Clinic", domain="abc.com"),
        make_candidate("ABC Dental Clinic Ltd", phone="+880 1712-345678"),
    ]
    clusters = deduplicate(cands)
    assert len(clusters) == 1
    assert len(clusters[0].candidates) == 3


def test_dedup_keeps_branches_separate():
    cands = [
        make_candidate(
            "ABC Dental - Dhanmondi", domain="abc.com",
            address="12 Road 5, Dhanmondi, Dhaka", google_place_id="P1",
        ),
        make_candidate(
            "ABC Dental - Gulshan", domain="abc.com",
            address="88 Gulshan Ave, Gulshan, Dhaka", google_place_id="P2",
        ),
    ]
    clusters = deduplicate(cands)
    assert len(clusters) == 2


def test_dedup_merges_same_name_same_address_across_providers():
    cands = [
        make_candidate("ABC Dental", address="12 Road 5, Dhanmondi, Dhaka", google_place_id="P1"),
        make_candidate("ABC Dental Clinic", address="12 Rd 5, Dhanmondi, Dhaka"),
    ]
    clusters = deduplicate(cands)
    assert len(clusters) == 1


def test_merged_candidate_prefers_place_data():
    cands = [
        make_candidate("ABC Dental", domain="abc.com"),
        make_candidate("ABC Dental", domain="abc.com", google_place_id="P9",
                       phone="+8801712345678", address="12 Rd, Dhaka", rating=4.5),
    ]
    merged = deduplicate(cands)[0].merged()
    assert merged.google_place_id == "P9"
    assert merged.rating == 4.5
