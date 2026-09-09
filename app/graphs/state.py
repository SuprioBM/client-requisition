"""Typed, serialisable LangGraph state.

Keep these flat and JSON-friendly (dicts / lists / primitives) so checkpointing
works and state stays inspectable. Domain objects are converted to dicts at the
node boundary.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class DiscoveryState(TypedDict, total=False):
    # inputs
    job_id: str
    industry: str
    city: str
    country: str
    radius_km: float
    target_leads: int

    # progress
    stage: str
    resolved_location: dict[str, Any]
    query_plan: dict[str, Any]

    # provider outputs (reducer: concatenate as nodes run)
    provider_runs: Annotated[list[dict[str, Any]], operator.add]
    candidates: Annotated[list[dict[str, Any]], operator.add]

    # pipeline outputs
    normalized_candidates: list[dict[str, Any]]
    cleaning: dict[str, Any]
    clusters: list[dict[str, Any]]
    summary: dict[str, Any]

    warnings: Annotated[list[str], operator.add]
    errors: Annotated[list[dict[str, Any]], operator.add]


class EvaluationState(TypedDict, total=False):
    job_id: str
    prospect_id: str

    stage: str
    prospect: dict[str, Any]
    research: dict[str, Any]
    research_run_id: str
    evidence: list[dict[str, Any]]

    pain_points: list[dict[str, Any]]
    solutions: list[dict[str, Any]]
    opportunity: dict[str, Any]
    score: dict[str, Any]
    evaluation_run_id: str

    outreach_strategy: dict[str, Any]
    email_draft: dict[str, Any]
    whatsapp_draft: dict[str, Any]
    approval_status: str

    warnings: Annotated[list[str], operator.add]
    errors: Annotated[list[dict[str, Any]], operator.add]
