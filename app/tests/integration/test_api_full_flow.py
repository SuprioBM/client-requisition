"""API-level walk through discovery -> prospect -> research -> evaluate ->
outreach -> approve, with mock providers + fake LLM (no network)."""

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

_SITE = """<html lang="en"><head><title>Bright Smiles</title>
<meta name="viewport" content="width=device-width"></head><body>
<h1>Bright Smiles Dental</h1><p>Call to book.</p><a href="tel:+880171">call</a></body></html>"""


@pytest.fixture(autouse=True)
def _wiring(respx_mock):
    register_handlers()
    llm_mod.set_llm_client(FakeLLMClient(DEFAULT_LLM_RESPONSES))
    set_provider_factory(
        lambda: [
            MockDiscoveryProvider(
                ProviderName.GOOGLE_PLACES,
                [make_candidate("Bright Smiles", google_place_id="P1",
                                website="https://brightsmiles.example",
                                domain="brightsmiles.example", phone="+8801712345678",
                                address="12 Dhanmondi, Dhaka", rating=4.4, review_count=30,
                                email="hello@brightsmiles.example")],
            )
        ]
    )
    respx_mock.route(host="brightsmiles.example").mock(
        return_value=httpx.Response(200, html=_SITE)
    )
    yield
    llm_mod.set_llm_client(None)
    set_provider_factory(None)


async def test_end_to_end_via_api(client):
    # 1. discovery
    r = await client.post("/api/v1/discovery/search", json={
        "country": "Bangladesh", "city": "Dhaka", "industry": "dentist", "target_leads": 5})
    job_id = r.json()["data"]["job_id"]
    await run_job(job_id)
    assert (await client.get(f"/api/v1/jobs/{job_id}")).json()["data"]["status"].startswith("COMPLETED")

    # 2. prospect list
    items = (await client.get("/api/v1/prospects")).json()["data"]["items"]
    assert len(items) == 1
    pid = items[0]["id"]

    # 3. research
    r = await client.post(f"/api/v1/prospects/{pid}/research")
    await run_job(r.json()["data"]["job_id"])
    research = (await client.get(f"/api/v1/prospects/{pid}/research")).json()["data"]
    assert research["evidence"]
    assert research["website_status"] == "ACTIVE"

    # 4. evaluate
    r = await client.post(f"/api/v1/prospects/{pid}/evaluate")
    await run_job(r.json()["data"]["job_id"])
    ev = (await client.get(f"/api/v1/prospects/{pid}/evaluation")).json()["data"]
    assert ev["is_opportunity"] is True
    assert 0 <= ev["score"]["total"] <= 100
    assert ev["pain_points"] and ev["pain_points"][0]["confidence"]

    # 5. profile aggregates everything
    prof = (await client.get(f"/api/v1/prospects/{pid}/profile")).json()["data"]
    assert prof["evaluation"]["score"]["total"] == ev["score"]["total"]
    assert prof["research"]["evidence"]

    # 6. outreach was drafted by the evaluation graph
    msgs = (await client.get(f"/api/v1/prospects/{pid}/outreach")).json()["data"]
    assert {m["channel"] for m in msgs} == {"EMAIL", "WHATSAPP"}
    email = next(m for m in msgs if m["channel"] == "EMAIL")
    assert email["status"] == "PENDING_APPROVAL"

    # 7. approve + send
    r = await client.post(f"/api/v1/outreach/{email['id']}/approve", json={"actor": "op"})
    assert r.json()["data"]["status"] == "APPROVED"
    r = await client.post(f"/api/v1/outreach/{email['id']}/send", json={})
    assert r.json()["data"]["status"] == "NOT_CONFIGURED"  # no fake send


async def test_evaluate_requires_prospect(client):
    r = await client.post("/api/v1/prospects/nope/evaluate")
    assert r.status_code == 404
