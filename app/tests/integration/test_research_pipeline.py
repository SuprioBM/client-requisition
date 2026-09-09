from __future__ import annotations

import httpx
from sqlalchemy import func, select

from app.db.models.prospect import Prospect
from app.db.models.research import Evidence, ResearchRun
from app.db.session import session_scope
from app.services.research_service import run_research

_SITE = """<html lang="en"><head><title>Bright Smiles Dhaka</title>
<meta name="viewport" content="width=device-width"></head><body>
<nav><a href="/services">Services</a><a href="/contact">Contact</a></nav>
<h1>Bright Smiles Dental</h1>
<p>We are a friendly dental practice. Call +880171111111 to arrange a visit.</p>
<a href="tel:+880171111111">Call</a>
</body></html>"""


async def _make_prospect(**kw) -> str:
    async with session_scope() as s:
        p = Prospect(
            business_name=kw.get("name", "Bright Smiles"),
            normalized_name="bright smiles",
            city="Dhaka", country="Bangladesh",
            website=kw.get("website"),
            rating=kw.get("rating"), review_count=kw.get("review_count"),
        )
        s.add(p)
        await s.flush()
        return p.id


async def test_research_persists_run_and_evidence(respx_mock):
    respx_mock.get("https://brightsmiles.example").mock(
        return_value=httpx.Response(200, html=_SITE, headers={"content-type": "text/html"})
    )
    respx_mock.get("https://brightsmiles.example/services").mock(
        return_value=httpx.Response(200, html=_SITE)
    )
    respx_mock.get("https://brightsmiles.example/contact").mock(
        return_value=httpx.Response(200, html=_SITE)
    )
    pid = await _make_prospect(website="https://brightsmiles.example", rating=4.2, review_count=15)

    out = await run_research(pid)
    assert out["status"] in ("COMPLETED", "PARTIAL")
    assert out["website_status"] == "ACTIVE"
    assert out["evidence_count"] > 0

    async with session_scope() as s:
        runs = await s.scalar(select(func.count()).select_from(ResearchRun))
        evs = await s.scalar(select(func.count()).select_from(Evidence))
        p = await s.get(Prospect, pid)
    assert runs == 1 and evs > 0
    assert p.last_researched_at is not None
    assert p.status == "RESEARCHED"


async def test_research_cache_hit_second_call(respx_mock):
    respx_mock.get("https://cache.example").mock(
        return_value=httpx.Response(200, html=_SITE)
    )
    pid = await _make_prospect(website="https://cache.example")
    first = await run_research(pid)
    second = await run_research(pid)
    assert first["cached"] is False
    assert second["cached"] is True
    async with session_scope() as s:
        runs = await s.scalar(select(func.count()).select_from(ResearchRun))
    assert runs == 1


async def test_research_website_timeout_is_partial(respx_mock):
    respx_mock.get("https://slow.example").mock(side_effect=httpx.ReadTimeout("slow"))
    pid = await _make_prospect(website="https://slow.example", rating=3.9, review_count=4)
    out = await run_research(pid)
    assert out["status"] == "PARTIAL"
    assert out["website_status"] in ("TIMEOUT", "UNKNOWN")
    # business-signal evidence still collected from discovery data
    assert out["evidence_count"] > 0


async def test_research_no_website_uses_business_signals_only(respx_mock):
    pid = await _make_prospect(website=None, rating=4.0, review_count=50)
    out = await run_research(pid)
    assert out["status"] == "PARTIAL"
    assert out["evidence_count"] > 0
