from __future__ import annotations

import httpx
import pytest

from app.db.models.enums import ProviderName
from app.discovery.registry import set_provider_factory
from app.evaluation import llm as llm_mod
from app.tests.mocks import (
    DEFAULT_LLM_RESPONSES,
    FakeLLMClient,
    MockDiscoveryProvider,
    make_candidate,
)
from app.workers.jobs import register_handlers, run_job


@pytest.fixture(autouse=True)
def _wiring(respx_mock):
    register_handlers()
    llm_mod.set_llm_client(FakeLLMClient(DEFAULT_LLM_RESPONSES))
    set_provider_factory(
        lambda: [
            MockDiscoveryProvider(
                ProviderName.GOOGLE_PLACES,
                [make_candidate("ABC Dental", google_place_id="P1",
                                website="https://abc.example", domain="abc.example",
                                phone="+8801712345678", address="12 Dhaka", rating=4.5,
                                review_count=40, email="hi@abc.example")],
            )
        ]
    )
    respx_mock.route(host="abc.example").mock(
        return_value=httpx.Response(200, html="<html><head><title>ABC</title></head><body>"
                                    "<h1>ABC Dental</h1><p>call us</p></body></html>")
    )
    yield
    llm_mod.set_llm_client(None)
    set_provider_factory(None)


async def test_dashboard_health_and_stats_and_activity(client):
    h = (await client.get("/api/v1/dashboard/health")).json()["data"]
    assert h["components"]["api"] == "online"
    assert h["components"]["database"] == "online"

    s = (await client.get("/api/v1/dashboard/stats")).json()["data"]
    assert "prospects" in s and "jobs" in s and "outreach" in s

    a = (await client.get("/api/v1/dashboard/activity")).json()["data"]
    assert isinstance(a, list)


async def test_jobs_list_and_retry_flow(client):
    r = await client.post("/api/v1/discovery/search", json={
        "country": "Bangladesh", "city": "Dhaka", "industry": "dentist", "target_leads": 5})
    job_id = r.json()["data"]["job_id"]
    await run_job(job_id)

    listing = (await client.get("/api/v1/jobs")).json()["data"]
    assert listing["total"] >= 1
    assert any(j["id"] == job_id for j in listing["items"])

    active = (await client.get("/api/v1/jobs?active_only=true")).json()["data"]
    assert all(j["status"] in ("QUEUED", "RUNNING") for j in active["items"])

    # provider analytics reflects the completed discovery job
    pa = (await client.get("/api/v1/dashboard/analytics/providers")).json()["data"]
    assert any(p["provider"] == "google_places" and p["results"] > 0 for p in pa)


async def test_job_sse_stream_reaches_done(client):
    r = await client.post("/api/v1/discovery/search", json={
        "country": "Bangladesh", "city": "Dhaka", "industry": "dentist", "target_leads": 5})
    job_id = r.json()["data"]["job_id"]
    await run_job(job_id)  # already terminal

    events: list[str] = []
    async with client.stream("GET", f"/api/v1/jobs/{job_id}/stream") as resp:
        assert resp.status_code == 200
        async for line in resp.aiter_lines():
            if line.startswith("event:"):
                events.append(line.split(":", 1)[1].strip())
            if "done" in events:
                break
    assert "job" in events and "done" in events


async def test_all_outreach_listing_and_save_draft(client):
    # discover -> evaluate (auto-drafts outreach)
    r = await client.post("/api/v1/discovery/search", json={
        "country": "Bangladesh", "city": "Dhaka", "industry": "dentist", "target_leads": 5})
    await run_job(r.json()["data"]["job_id"])
    pid = (await client.get("/api/v1/prospects")).json()["data"]["items"][0]["id"]
    r = await client.post(f"/api/v1/prospects/{pid}/evaluate")
    await run_job(r.json()["data"]["job_id"])

    outreach = (await client.get("/api/v1/outreach")).json()["data"]
    assert outreach["total"] >= 2
    msg = next(m for m in outreach["items"] if m["channel"] == "EMAIL")
    assert msg["business_name"]

    saved = await client.patch(f"/api/v1/outreach/{msg['id']}",
                               json={"subject": "Edited subject", "body": "Edited body text"})
    assert saved.json()["data"]["subject"] == "Edited subject"
    assert saved.json()["data"]["body"] == "Edited body text"


async def test_bulk_research_and_evaluate(client):
    r = await client.post("/api/v1/discovery/search", json={
        "country": "Bangladesh", "city": "Dhaka", "industry": "dentist", "target_leads": 5})
    await run_job(r.json()["data"]["job_id"])
    ids = [p["id"] for p in (await client.get("/api/v1/prospects")).json()["data"]["items"]]

    br = await client.post("/api/v1/prospects/bulk/research", json={"prospect_ids": ids})
    assert br.status_code == 200
    assert len(br.json()["data"]["queued"]) == len(ids)

    be = await client.post("/api/v1/prospects/bulk/evaluate", json={"prospect_ids": ids})
    assert be.status_code == 200
    assert len(be.json()["data"]["queued"]) == len(ids)
