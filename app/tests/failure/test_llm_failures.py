from __future__ import annotations

import httpx
import pytest
from sqlalchemy import func, select

from app.core.exceptions import LLMError
from app.db.models.evaluation import EvaluationRun
from app.db.models.prospect import Prospect
from app.db.models.research import ResearchRun
from app.db.session import session_scope
from app.evaluation import llm as llm_mod
from app.evaluation.llm import LLMClient
from app.services.evaluation_service import run_evaluation

_SITE = "<html><head><title>X</title></head><body><h1>Clinic</h1><p>call us</p></body></html>"


class _BadBackend:
    model_name = "bad"
    calls = 0

    async def complete_json(self, system, user):
        _BadBackend.calls += 1
        return "not json at all { oops", {"model": "bad"}


class _RateThenOkBackend:
    model_name = "rl"

    def __init__(self):
        self.calls = 0

    async def complete_json(self, system, user):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("Error code: 429 rate limit reached. try again in 0.1s")
        return '{"pain_points": []}', {"model": "rl"}


@pytest.fixture
def _prospect_site(respx_mock):
    respx_mock.route(host="clinic.example").mock(return_value=httpx.Response(200, html=_SITE))


async def _mk_prospect() -> str:
    async with session_scope() as s:
        p = Prospect(business_name="Clinic", normalized_name="clinic", industry="dentist",
                     city="Dhaka", country="Bangladesh", website="https://clinic.example",
                     rating=4.0, review_count=20)
        s.add(p)
        await s.flush()
        return p.id


async def test_malformed_llm_output_fails_cleanly_and_preserves_research(_prospect_site):
    _BadBackend.calls = 0
    llm_mod.set_llm_client(LLMClient(backend=_BadBackend()))
    try:
        pid = await _mk_prospect()
        with pytest.raises(LLMError) as ei:
            await run_evaluation(pid)
        assert ei.value.code.value == "LLM_INVALID_OUTPUT"
        assert _BadBackend.calls == 2  # one constrained retry

        async with session_scope() as s:
            # research still persisted, evaluation run marked FAILED
            assert await s.scalar(select(func.count()).select_from(ResearchRun)) == 1
            run = (await s.execute(select(EvaluationRun))).scalar_one()
            assert run.status == "FAILED"
    finally:
        llm_mod.set_llm_client(None)


async def test_rate_limit_is_retried_then_succeeds():
    from app.schemas.evaluation import PainPointList

    backend = _RateThenOkBackend()
    model, meta = await LLMClient(backend=backend).structured(
        "pain_points", PainPointList, "prompt"
    )
    assert backend.calls == 2  # 429 once, then success
    assert model.pain_points == []
    assert meta["status"] == "ok"
