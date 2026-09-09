from __future__ import annotations

from app.workers import queue


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "ok"


async def test_readiness_reports_capabilities(client):
    r = await client.get("/health/ready")
    body = r.json()["data"]
    assert "database" in body["checks"]
    assert "capabilities" in body


async def test_plan_preview(client):
    r = await client.post(
        "/api/v1/discovery/plan-preview",
        json={"country": "Bangladesh", "city": "Dhaka", "industry": "dentist"},
    )
    assert r.status_code == 200
    assert len(r.json()["data"]["queries"]) >= 1


async def test_discovery_search_creates_and_enqueues_job(client):
    r = await client.post(
        "/api/v1/discovery/search",
        json={
            "country": "Bangladesh",
            "city": "Dhaka",
            "industry": "dentist",
            "radius_km": 10,
            "target_leads": 10,
        },
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["data"]["job_id"]
    assert r.json()["data"]["status"] == "QUEUED"

    # job is retrievable
    r2 = await client.get(f"/api/v1/jobs/{job_id}")
    assert r2.status_code == 200
    assert r2.json()["data"]["job_type"] == "DISCOVERY"

    # and it landed on the queue
    assert await queue.depth() == 1


async def test_discovery_search_requires_api_key(client):
    r = await client.post(
        "/api/v1/discovery/search",
        headers={"X-API-Key": "nope"},
        json={"country": "Bangladesh", "city": "Dhaka", "industry": "dentist"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


async def test_unknown_job_returns_structured_404(client):
    r = await client.get("/api/v1/jobs/does-not-exist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "JOB_NOT_FOUND"


async def test_validation_error_shape(client):
    r = await client.post("/api/v1/discovery/search", json={"city": "Dhaka"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
