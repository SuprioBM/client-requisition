from __future__ import annotations

import httpx
import pytest
from sqlalchemy import func, select

from app.db.models.enums import OutreachStatus
from app.db.models.evaluation import EvaluationRun, PainPoint, Solution
from app.db.models.outreach import OutreachMessage
from app.db.models.prospect import Prospect
from app.db.session import session_scope
from app.evaluation import llm as llm_mod
from app.services import outreach_service
from app.services.evaluation_service import run_evaluation
from app.tests.mocks import DEFAULT_LLM_RESPONSES, FakeLLMClient

_SITE = """<html lang="en"><head><title>Bright Smiles</title>
<meta name="viewport" content="width=device-width"></head><body>
<nav><a href="/services">Services</a><a href="/contact">Contact</a></nav>
<h1>Bright Smiles Dental</h1><p>Call us to book an appointment.</p>
<a href="tel:+880171111111">Call</a></body></html>"""


@pytest.fixture(autouse=True)
def _fake_llm():
    llm_mod.set_llm_client(FakeLLMClient(DEFAULT_LLM_RESPONSES))
    yield
    llm_mod.set_llm_client(None)


async def _prospect(**kw) -> str:
    async with session_scope() as s:
        p = Prospect(
            business_name=kw.get("name", "Bright Smiles"), normalized_name="bright smiles",
            industry="dentist", city="Dhaka", country="Bangladesh",
            website=kw.get("website"), email=kw.get("email", "hello@brightsmiles.example"),
            phone=kw.get("phone", "+880171111111"),
            rating=kw.get("rating", 4.3), review_count=kw.get("review_count", 22),
        )
        s.add(p)
        await s.flush()
        return p.id


async def test_full_evaluation_produces_evidence_backed_output(respx_mock):
    respx_mock.get("https://brightsmiles.example").mock(
        return_value=httpx.Response(200, html=_SITE)
    )
    respx_mock.route(host="brightsmiles.example").mock(
        return_value=httpx.Response(200, html=_SITE)
    )
    pid = await _prospect(website="https://brightsmiles.example")

    result = await run_evaluation(pid)

    assert result["is_opportunity"] is True
    assert 0 <= result["score"]["total"] <= 100
    assert result["score"]["evidence_confidence"] <= 20
    assert len(result["pain_points"]) >= 1
    assert result["outreach"]["generated"] is True

    async with session_scope() as s:
        assert await s.scalar(select(func.count()).select_from(EvaluationRun)) == 1
        assert await s.scalar(select(func.count()).select_from(PainPoint)) >= 1
        assert await s.scalar(select(func.count()).select_from(Solution)) >= 1
        msgs = (await s.execute(select(OutreachMessage))).scalars().all()
        assert {m.channel for m in msgs} == {"EMAIL", "WHATSAPP"}
        assert all(m.status == OutreachStatus.PENDING_APPROVAL.value for m in msgs)
        p = await s.get(Prospect, pid)
        assert p.status == "OUTREACH_DRAFTED"


async def test_no_evidence_caps_evidence_confidence(respx_mock):
    # unreachable site + no reviews -> weak evidence
    respx_mock.route(host="void.example").mock(side_effect=httpx.ConnectError("no"))
    pid = await _prospect(website="https://void.example", rating=None, review_count=None)

    result = await run_evaluation(pid)
    # unreachable site + no reviews -> at most a weak website-status evidence item
    assert result["score"]["evidence_confidence"] <= 8


async def test_approval_then_send_is_not_configured(respx_mock):
    respx_mock.route(host="brightsmiles.example").mock(
        return_value=httpx.Response(200, html=_SITE)
    )
    pid = await _prospect(website="https://brightsmiles.example")
    result = await run_evaluation(pid)
    email_id = next(m["id"] for m in result["outreach"]["messages"] if m["channel"] == "EMAIL")

    # cannot send before approval
    with pytest.raises(Exception):
        await outreach_service.send(email_id, actor="t")

    await outreach_service.approve(email_id, actor="tester")
    sent = await outreach_service.send(email_id, actor="tester")
    assert sent["status"] == "NOT_CONFIGURED"  # never a fake SENT

    async with session_scope() as s:
        m = await s.get(OutreachMessage, email_id)
        assert m.status == "NOT_CONFIGURED"
        assert m.approved_by == "tester"


async def test_duplicate_outreach_blocked(respx_mock):
    respx_mock.route(host="brightsmiles.example").mock(
        return_value=httpx.Response(200, html=_SITE)
    )
    pid = await _prospect(website="https://brightsmiles.example")
    await run_evaluation(pid)
    second = await run_evaluation(pid, force_research=False)
    assert set(second["outreach"]["blocked_duplicate"]) == {"EMAIL", "WHATSAPP"}
