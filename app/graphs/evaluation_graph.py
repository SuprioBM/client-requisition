"""LangGraph evaluation graph.

load_prospect -> research_business -> collect_evidence -> detect_pain_points
 -> map_solutions -> evaluate_opportunity -> score_lead -> finalize_evaluation
 -> (opportunity?) -> generate_outreach_strategy -> generate_email
 -> generate_whatsapp -> persist_outreach -> human_approval -> END

Stage-level resumability comes from the LangGraph checkpointer keyed by
thread_id == job_id: a failure in one node, on retry, resumes from that node
with all earlier node results intact.
"""

from __future__ import annotations

import os
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.core.logging import get_logger
from app.db.models.enums import OutreachChannel, OutreachStatus, ProspectStatus
from app.db.models.prospect import Prospect
from app.db.repositories.evaluation import EvaluationRepository
from app.db.repositories.outreach import OutreachRepository
from app.db.repositories.research import ResearchRepository
from app.db.session import session_scope
from app.evaluation import steps
from app.evaluation.llm import get_llm
from app.evaluation.prompts import PROMPT_VERSION, SCORING_VERSION
from app.evaluation.scoring import compute_score
from app.graphs.state import EvaluationState
from app.schemas.evaluation import LeadScoreInput
from app.services.research_service import run_research

log = get_logger(__name__)

SENDER_NAME = os.environ.get("OUTREACH_SENDER_NAME", "Suprio")

EVALUATION_STAGES = [
    "load_prospect",
    "research_business",
    "collect_evidence",
    "detect_pain_points",
    "map_solutions",
    "evaluate_opportunity",
    "score_lead",
    "finalize_evaluation",
    "generate_outreach_strategy",
    "generate_email",
    "generate_whatsapp",
    "persist_outreach",
    "human_approval",
]


async def load_prospect(state: EvaluationState) -> dict:
    async with session_scope() as s:
        p = await s.get(Prospect, state["prospect_id"])
        if p is None:
            return {"stage": "load_prospect",
                    "errors": [{"code": "NOT_FOUND", "message": "prospect missing"}]}
        if p.status in (ProspectStatus.DISCOVERED.value, ProspectStatus.RESEARCHED.value):
            p.status = ProspectStatus.EVALUATING.value
        prospect = {
            "id": p.id, "business_name": p.business_name, "industry": p.industry,
            "city": p.city, "country": p.country, "website": p.website,
            "phone": p.phone, "email": p.email, "rating": p.rating,
            "review_count": p.review_count, "provider_metadata": p.provider_metadata or {},
        }
    return {"stage": "load_prospect", "prospect": prospect}


async def research_business(state: EvaluationState) -> dict:
    res = await run_research(state["prospect_id"], job_id=state.get("job_id"), force=False)
    return {
        "stage": "research_business",
        "research_run_id": res["research_run_id"],
        "research": {"website_status": res.get("website_status"),
                     "sources_used": res.get("sources_used", [])},
        "score": {"_signals": res.get("signals", {})},  # carried for scoring
    }


async def collect_evidence(state: EvaluationState) -> dict:
    async with session_scope() as s:
        rows = await ResearchRepository(s).evidence_for_run(state["research_run_id"])
        evidence = [
            {"id": e.id, "evidence_type": e.evidence_type, "source_type": e.source_type,
             "source_url": e.source_url, "observation": e.observation,
             "confidence": e.confidence, "data_origin": e.data_origin}
            for e in rows
        ]
    log.info("evaluation.evidence.collected", count=len(evidence))
    return {"stage": "collect_evidence", "evidence": evidence}


def _signals(state: EvaluationState) -> dict:
    return (state.get("score") or {}).get("_signals", {})


async def detect_pain_points(state: EvaluationState) -> dict:
    model, meta = await steps.detect_pain_points(
        state["prospect"], _signals(state), state.get("evidence", [])
    )
    return {"stage": "detect_pain_points",
            "pain_points": [p.model_dump() for p in model.pain_points]}


async def map_solutions(state: EvaluationState) -> dict:
    model, meta = await steps.map_solutions(state["prospect"], state.get("pain_points", []))
    solutions = sorted(
        (s.model_dump() for s in model.solutions), key=lambda x: x.get("fit_rank", 99)
    )
    return {"stage": "map_solutions", "solutions": solutions}


async def evaluate_opportunity(state: EvaluationState) -> dict:
    model, meta = await steps.evaluate_opportunity(
        state["prospect"], _signals(state), state.get("pain_points", []),
        state.get("solutions", []), state.get("evidence", []),
    )
    return {"stage": "evaluate_opportunity", "opportunity": model.model_dump()}


async def score_lead(state: EvaluationState) -> dict:
    raw, meta = await steps.propose_subscores(
        state["opportunity"], state.get("pain_points", []), state.get("solutions", []),
        _signals(state),
    )
    score = compute_score(
        raw if isinstance(raw, LeadScoreInput) else LeadScoreInput.model_validate(raw),
        is_opportunity=bool(state["opportunity"].get("is_opportunity")),
        evidence=state.get("evidence", []),
    )
    return {"stage": "score_lead", "score": {**score, "_signals": _signals(state)}}


async def finalize_evaluation(state: EvaluationState) -> dict:
    score = {k: v for k, v in (state.get("score") or {}).items() if k != "_signals"}
    async with session_scope() as s:
        erepo = EvaluationRepository(s)
        run = await erepo.create_run(
            state["prospect_id"], research_run_id=state.get("research_run_id"),
            job_id=state.get("job_id"), prompt_version=PROMPT_VERSION,
            scoring_version=SCORING_VERSION, model=get_llm().model_name,
        )
        await erepo.finalize(
            run, opportunity=state["opportunity"], score=score,
            pain_points=state.get("pain_points", []), solutions=state.get("solutions", []),
            llm_meta={"graph": True},
        )
        run_id = run.id
    return {"stage": "finalize_evaluation", "evaluation_run_id": run_id}


async def generate_outreach_strategy(state: EvaluationState) -> dict:
    model, meta = await steps.generate_strategy(
        state["prospect"], state["opportunity"], state.get("pain_points", []),
        state.get("solutions", []), state.get("evidence", []),
    )
    return {"stage": "generate_outreach_strategy", "outreach_strategy": model.model_dump()}


async def generate_email(state: EvaluationState) -> dict:
    model, meta = await steps.generate_email(
        state["prospect"], state["outreach_strategy"], SENDER_NAME
    )
    return {"stage": "generate_email", "email_draft": model.model_dump()}


async def generate_whatsapp(state: EvaluationState) -> dict:
    model, meta = await steps.generate_whatsapp(
        state["prospect"], state["outreach_strategy"], SENDER_NAME
    )
    return {"stage": "generate_whatsapp", "whatsapp_draft": model.model_dump()}


async def persist_outreach(state: EvaluationState) -> dict:
    strategy = state["outreach_strategy"]
    email = state["email_draft"]
    wa = state["whatsapp_draft"]
    created: list[dict] = []
    blocked: list[str] = []
    async with session_scope() as s:
        repo = OutreachRepository(s)
        prospect = await s.get(Prospect, state["prospect_id"])
        specs = [
            (OutreachChannel.EMAIL, email.get("subject"), email.get("body"),
             prospect.email if prospect else None),
            (OutreachChannel.WHATSAPP, None, wa.get("body"),
             prospect.phone if prospect else None),
        ]
        for channel, subject, body, to_addr in specs:
            if await repo.recent_message(state["prospect_id"], channel) is not None:
                blocked.append(channel.value)
                continue
            msg = await repo.create(
                prospect_id=state["prospect_id"],
                evaluation_run_id=state.get("evaluation_run_id"),
                channel=channel, strategy=strategy, subject=subject, body=body or "",
                to_address=to_addr, prompt_version=PROMPT_VERSION, llm_meta={"graph": True},
                evidence_ids=strategy.get("evidence_ids", []),
                status=OutreachStatus.PENDING_APPROVAL,
            )
            created.append({"id": msg.id, "channel": channel.value})
        if prospect and created and prospect.status == ProspectStatus.EVALUATED.value:
            prospect.status = ProspectStatus.OUTREACH_DRAFTED.value
    return {"stage": "persist_outreach",
            "warnings": [f"duplicate outreach blocked: {c}" for c in blocked],
            "email_draft": {**email, "_message_ids": created}}


async def human_approval(state: EvaluationState) -> dict:
    log.info("evaluation.human_approval.pending", prospect_id=state["prospect_id"])
    return {"stage": "human_approval", "approval_status": "PENDING_APPROVAL"}


def _route_after_finalize(state: EvaluationState) -> str:
    opp = state.get("opportunity") or {}
    if opp.get("is_opportunity") and opp.get("outreach_worthwhile"):
        return "generate_outreach_strategy"
    return END


def build_evaluation_graph(checkpointer: Any = None):
    g: StateGraph = StateGraph(EvaluationState)
    for fn in (
        load_prospect, research_business, collect_evidence, detect_pain_points,
        map_solutions, evaluate_opportunity, score_lead, finalize_evaluation,
        generate_outreach_strategy, generate_email, generate_whatsapp,
        persist_outreach, human_approval,
    ):
        g.add_node(fn.__name__, fn)

    g.add_edge(START, "load_prospect")
    g.add_edge("load_prospect", "research_business")
    g.add_edge("research_business", "collect_evidence")
    g.add_edge("collect_evidence", "detect_pain_points")
    g.add_edge("detect_pain_points", "map_solutions")
    g.add_edge("map_solutions", "evaluate_opportunity")
    g.add_edge("evaluate_opportunity", "score_lead")
    g.add_edge("score_lead", "finalize_evaluation")
    g.add_conditional_edges("finalize_evaluation", _route_after_finalize,
                            ["generate_outreach_strategy", END])
    g.add_edge("generate_outreach_strategy", "generate_email")
    g.add_edge("generate_email", "generate_whatsapp")
    g.add_edge("generate_whatsapp", "persist_outreach")
    g.add_edge("persist_outreach", "human_approval")
    g.add_edge("human_approval", END)
    return g.compile(checkpointer=checkpointer)
