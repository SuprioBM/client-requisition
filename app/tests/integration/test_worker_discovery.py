from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.db.models.enums import JobStatus, JobType, ProviderName
from app.db.models.job import Job
from app.db.models.prospect import Prospect
from app.db.session import session_scope
from app.discovery.registry import set_provider_factory
from app.services.job_service import create_and_enqueue
from app.tests.mocks import MockDiscoveryProvider, make_candidate
from app.workers.jobs import register_handlers, run_job


@pytest.fixture(autouse=True)
def _handlers():
    register_handlers()
    yield
    set_provider_factory(None)


async def _new_discovery_job(params: dict | None = None) -> str:
    async with session_scope() as s:
        job = await create_and_enqueue(
            s,
            JobType.DISCOVERY,
            params or {"industry": "dentist", "city": "Dhaka", "country": "Bangladesh",
                      "radius_km": 10, "target_leads": 10},
        )
        return job.id


async def _get_job(job_id: str) -> Job:
    async with session_scope() as s:
        return await s.get(Job, job_id)


async def test_worker_runs_discovery_job_end_to_end():
    set_provider_factory(
        lambda: [
            MockDiscoveryProvider(
                ProviderName.GOOGLE_PLACES,
                [
                    make_candidate("ABC Dental", google_place_id="P1", domain="abcdental.com",
                                   phone="+8801712345678", address="12 Dhanmondi, Dhaka", rating=4.6),
                    make_candidate("Smile Studio", google_place_id="P2", address="9 Gulshan, Dhaka"),
                ],
            )
        ]
    )
    job_id = await _new_discovery_job()
    await run_job(job_id)

    job = await _get_job(job_id)
    assert job.status in (JobStatus.COMPLETED.value, JobStatus.COMPLETED_WITH_WARNINGS.value)
    assert job.result["prospects_created"] == 2
    assert job.current_stage == "COMPLETED"

    async with session_scope() as s:
        total = await s.scalar(select(func.count()).select_from(Prospect))
    assert total == 2


async def test_all_providers_fail_eventually_marks_job_failed():
    set_provider_factory(
        lambda: [MockDiscoveryProvider(ProviderName.GOOGLE_PLACES, fail_with="PROVIDER_UNAVAILABLE")]
    )
    job_id = await _new_discovery_job()

    for _ in range(6):
        job = await _get_job(job_id)
        if job.status == JobStatus.FAILED.value:
            break
        await run_job(job_id)

    job = await _get_job(job_id)
    assert job.status == JobStatus.FAILED.value
    assert job.error_code == "PROVIDER_UNAVAILABLE"
    assert job.retry_count == job.max_retries
