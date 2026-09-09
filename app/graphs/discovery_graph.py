"""LangGraph discovery graph.

START -> validate_search -> resolve_location -> plan_queries
      -> google_discovery -> duckduckgo_discovery -> brave_discovery
      -> aggregate -> normalize -> clean -> deduplicate -> save -> END

Provider nodes never abort the graph on provider-side failure; they append a
failed ProviderRun to state["provider_runs"] and move on. If every attempted
provider fails, `save` records the job outcome accordingly.
"""

from __future__ import annotations

import asyncio
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.core.logging import get_logger
from app.db.models.enums import ProviderName, RecordKind
from app.db.repositories.prospects import ProspectRepository
from app.db.session import session_scope
from app.discovery.base import BusinessCandidate, ProviderRun
from app.discovery.cleaner import clean_candidates
from app.discovery.deduplicator import deduplicate
from app.discovery.location import resolve_location
from app.discovery.normalizer import canonical_domain, normalize_website
from app.discovery.planner import plan_queries as _plan_place
from app.discovery.planner import plan_web_search_queries as _plan_web
from app.discovery.registry import build_discovery_providers
from app.graphs.state import DiscoveryState

log = get_logger(__name__)

_WEB_PROVIDERS = {ProviderName.DUCKDUCKGO, ProviderName.BRAVE}

# Ordered stage names as reported in state["stage"] — drives the dashboard pipeline view.
DISCOVERY_STAGES = [
    "validate_search",
    "resolve_location",
    "plan_queries",
    "google_places_discovery",
    "duckduckgo_discovery",
    "brave_discovery",
    "aggregate",
    "normalize",
    "clean",
    "deduplicate",
    "save",
]


def _providers_by_name() -> dict[ProviderName, Any]:
    return {p.name: p for p in build_discovery_providers()}


async def validate_search(state: DiscoveryState) -> dict:
    missing = [k for k in ("industry", "city", "country") if not state.get(k)]
    if missing:
        return {"stage": "validate_search", "errors": [{"code": "VALIDATION_ERROR",
                "message": f"missing fields: {missing}"}]}
    return {"stage": "validate_search"}


async def resolve_location_node(state: DiscoveryState) -> dict:
    loc = await resolve_location(state["city"], state["country"])
    log.info("location.resolved", city=loc.city, country=loc.country, source=loc.source)
    return {"stage": "resolve_location", "resolved_location": loc.model_dump(mode="json")}


async def plan_queries_node(state: DiscoveryState) -> dict:
    loc = state["resolved_location"]
    place = _plan_place(state["industry"], loc["city"], loc["country"])
    web = _plan_web(state["industry"], loc["city"], loc["country"])
    log.info("plan.queries", place_queries=place, web_queries=web)
    return {"stage": "plan_queries", "query_plan": {"place_queries": place, "web_queries": web}}


async def _run_provider(name: ProviderName, state: DiscoveryState) -> dict:
    providers = _providers_by_name()
    provider = providers.get(name)
    if provider is None:
        return {"stage": f"{name.value}_discovery",
                "provider_runs": [ProviderRun(provider=name, query="", status="skipped",
                                              error_code="PROVIDER_UNAVAILABLE").model_dump(mode="json")]}
    if not await provider.available():
        return {"stage": f"{name.value}_discovery",
                "provider_runs": [ProviderRun(provider=name, query="", status="skipped",
                                              error_code="CONFIG_MISSING").model_dump(mode="json")]}

    loc = state["resolved_location"]
    plan = state["query_plan"]
    queries = plan["web_queries"] if name in _WEB_PROVIDERS else plan["place_queries"]

    async def _q(query: str) -> ProviderRun:
        try:
            return await provider.search(
                query, city=loc["city"], country=loc["country"],
                latitude=loc.get("latitude"), longitude=loc.get("longitude"),
                radius_km=state.get("radius_km", 10.0),
                limit=max(20, state.get("target_leads", 60)),
            )
        except Exception as exc:  # noqa: BLE001 - provider bug contained
            log.error("discovery.provider.crashed", provider=name.value, query=query,
                      error=str(exc), exc_info=True)
            return ProviderRun(provider=name, query=query, status="failed",
                               error_code="PROVIDER_BAD_RESPONSE", error_message=str(exc))

    runs = await asyncio.gather(*[_q(q) for q in queries])
    candidates: list[dict] = []
    for r in runs:
        candidates.extend(c.model_dump(mode="json") for c in r.candidates)
    return {
        "stage": f"{name.value}_discovery",
        "provider_runs": [r.model_dump(mode="json") for r in runs],
        "candidates": candidates,
    }


async def google_discovery(state: DiscoveryState) -> dict:
    return await _run_provider(ProviderName.GOOGLE_PLACES, state)


async def duckduckgo_discovery(state: DiscoveryState) -> dict:
    return await _run_provider(ProviderName.DUCKDUCKGO, state)


async def brave_discovery(state: DiscoveryState) -> dict:
    return await _run_provider(ProviderName.BRAVE, state)


async def aggregate(state: DiscoveryState) -> dict:
    runs = state.get("provider_runs", [])
    attempted = [r for r in runs if r.get("status") != "skipped"]
    any_ok = any(r.get("status") in ("ok", "partial") for r in attempted)
    warnings: list[str] = []
    for r in runs:
        if r.get("status") == "failed":
            warnings.append(f"{r['provider']} failed: {r.get('error_code')}")
    log.info("discovery.aggregate", providers=len(runs), candidates=len(state.get("candidates", [])),
             any_ok=any_ok)
    return {"stage": "aggregate", "warnings": warnings,
            "summary": {"any_provider_succeeded": any_ok, "attempted": len(attempted)}}


async def normalize(state: DiscoveryState) -> dict:
    out: list[dict] = []
    for candidate in state.get("candidates", []):
        c = dict(candidate)
        if c.get("website"):
            c["website"] = normalize_website(c["website"]) or c["website"]
        if c.get("website") and not c.get("domain"):
            c["domain"] = canonical_domain(c["website"])
        out.append(c)
    log.info("normalization.completed", input=len(state.get("candidates", [])), output=len(out))
    return {"stage": "normalize", "normalized_candidates": out}


def _candidates_from(state: DiscoveryState) -> list[BusinessCandidate]:
    raw = state.get("normalized_candidates") or state.get("candidates", [])
    return [BusinessCandidate.model_validate(c) for c in raw]


async def clean(state: DiscoveryState) -> dict:
    cands = _candidates_from(state)
    res = clean_candidates(cands)
    return {
        "stage": "clean",
        "cleaning": {
            "kept": [c.model_dump(mode="json") for c in res.kept],
            "reviewed": [c.model_dump(mode="json") for c in res.reviewed],
            "dropped": res.dropped,
        },
    }


async def deduplicate_node(state: DiscoveryState) -> dict:
    cleaning = state["cleaning"]
    kept = [BusinessCandidate.model_validate(c) for c in cleaning["kept"] + cleaning["reviewed"]]
    review_identities = {
        BusinessCandidate.model_validate(c).source_identity() for c in cleaning["reviewed"]
    }
    clusters = deduplicate(kept)
    payload = []
    for cl in clusters:
        payload.append(
            {
                "candidates": [c.model_dump(mode="json") for c in cl.candidates],
                "needs_review": all(
                    c.source_identity() in review_identities for c in cl.candidates
                ),
            }
        )
    return {"stage": "deduplicate", "clusters": payload}


async def save(state: DiscoveryState) -> dict:
    from app.discovery.deduplicator import ProspectCluster

    loc = state["resolved_location"]
    created = updated = 0
    ids: list[str] = []
    async with session_scope() as session:
        repo = ProspectRepository(session)
        for entry in state.get("clusters", []):
            cluster = ProspectCluster(
                candidates=[BusinessCandidate.model_validate(c) for c in entry["candidates"]]
            )
            prospect, was_created = await repo.upsert_from_cluster(
                cluster,
                industry=state["industry"],
                country=loc["country"],
                city=loc["city"],
                job_id=state.get("job_id"),
                needs_review=entry.get("needs_review", False),
                record_kind=RecordKind.REAL,
            )
            ids.append(prospect.id)
            created += int(was_created)
            updated += int(not was_created)

    summary = {
        **state.get("summary", {}),
        "resolved_location": loc,
        "query_plan": state.get("query_plan", {}),
        "provider_runs": state.get("provider_runs", []),
        "raw_candidates": len(state.get("candidates", [])) or state.get("summary", {}).get(
            "raw_candidates", 0
        ),
        "unique_clusters": len(state.get("clusters", [])),
        "prospects_created": created,
        "prospects_updated": updated,
        "prospect_ids": ids,
        "warnings": state.get("warnings", []),
    }
    log.info("discovery.save.completed", created=created, updated=updated, unique=len(ids))
    return {"stage": "save", "summary": summary}


def build_discovery_graph(checkpointer: Any = None):
    g: StateGraph = StateGraph(DiscoveryState)
    g.add_node("validate_search", validate_search)
    g.add_node("resolve_location", resolve_location_node)
    g.add_node("plan_queries", plan_queries_node)
    g.add_node("google_discovery", google_discovery)
    g.add_node("duckduckgo_discovery", duckduckgo_discovery)
    g.add_node("brave_discovery", brave_discovery)
    g.add_node("aggregate", aggregate)
    g.add_node("normalize", normalize)
    g.add_node("clean", clean)
    g.add_node("deduplicate", deduplicate_node)
    g.add_node("save", save)

    g.add_edge(START, "validate_search")
    g.add_edge("validate_search", "resolve_location")
    g.add_edge("resolve_location", "plan_queries")
    g.add_edge("plan_queries", "google_discovery")
    g.add_edge("google_discovery", "duckduckgo_discovery")
    g.add_edge("duckduckgo_discovery", "brave_discovery")
    g.add_edge("brave_discovery", "aggregate")
    g.add_edge("aggregate", "normalize")
    g.add_edge("normalize", "clean")
    g.add_edge("clean", "deduplicate")
    g.add_edge("deduplicate", "save")
    g.add_edge("save", END)
    return g.compile(checkpointer=checkpointer)
