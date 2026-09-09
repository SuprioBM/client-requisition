from __future__ import annotations

from app.discovery.planner import expand_industry, plan_queries, plan_web_search_queries


def test_known_industry_expands_to_synonyms():
    qs = expand_industry("Dentist")
    assert "dental clinic" in [q.lower() for q in qs]
    assert len(qs) >= 3


def test_unknown_industry_gets_generic_expansion():
    qs = expand_industry("underwater basket weaving")
    assert any("underwater basket weaving" in q.lower() for q in qs)


def test_plan_queries_is_capped_and_deduped():
    qs = plan_queries("dentist", "Dhaka", "Bangladesh")
    assert len(qs) <= 6
    assert len(qs) == len({q.lower() for q in qs})


def test_web_search_queries_include_location():
    qs = plan_web_search_queries("dentist", "Dhaka", "Bangladesh")
    assert all("dhaka" in q.lower() for q in qs)
