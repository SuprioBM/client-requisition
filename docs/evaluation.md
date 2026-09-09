# Evaluation

Understands a business. Answers "is there a real, evidence-backed opportunity?"

## Graph (`app/graphs/evaluation_graph.py`)

```
load_prospect -> research_business -> collect_evidence -> detect_pain_points
 -> map_solutions -> evaluate_opportunity -> score_lead -> finalize_evaluation
 -> (is_opportunity && outreach_worthwhile?) -> generate_outreach_strategy
 -> generate_email -> generate_whatsapp -> persist_outreach -> human_approval
```

Stage-level resumability: the LangGraph checkpointer is keyed by
`thread_id == job_id`. A failure in one node, on job retry, resumes from that
node with earlier node outputs intact — research/evidence are not recomputed.

## Deterministic vs LLM

| Deterministic | LLM (Groq via LangChain) |
|---|---|
| loading data, collecting evidence, **score arithmetic**, clamping, guard-rails, persistence, retries | pain-point detection, solution mapping, opportunity reasoning, sub-score proposal, outreach copy |

## LLM client (`app/evaluation/llm.py`)

- `ChatGroq` with `response_format: json_object`.
- Response parsed and validated against a Pydantic schema
  (`app/schemas/evaluation.py`). Invalid → **one constrained retry**
  ("return ONLY minified JSON with keys […]") → else `LLM_INVALID_OUTPUT`.
- Rate limits (429) are retried up to 4× honoring the "try again in Xs" hint.
- Errors mapped: `LLM_TIMEOUT`, `LLM_RATE_LIMITED`, `LLM_AUTH_FAILED`,
  `LLM_INVALID_OUTPUT`, `LLM_UNAVAILABLE`.
- Every call logs `label`, `attempts`, `latency_ms`, `model`, token usage.
- Injectable: `set_llm_client(FakeLLMClient(...))` for tests (zero network).

## Hallucination control

The evaluator system prompt is explicit: use only supplied evidence, cite
evidence ids, `NOT_ENOUGH_EVIDENCE` when unsupported, never fabricate processes /
tech / budgets / willingness to pay, prefer conservative conclusions.

## Pain points → solutions → opportunity

- **Pain points**: `{category, title, description, evidence_ids[], confidence}`
  where confidence ∈ `CONFIRMED|LIKELY|POSSIBLE|NOT_ENOUGH_EVIDENCE`. Empty list
  is a valid answer.
- **Solutions**: mapped from the configurable catalogue
  (`services_kb.py`, override via `SERVICES_KB_PATH`), ranked by `fit_rank`.
  Outreach later focuses on the single strongest fit.
- **Opportunity**: `is_opportunity`, `commercial_potential`
  (`LOW|MEDIUM|HIGH|UNKNOWN` — never a fake budget), `contactable`,
  `outreach_worthwhile`, with cited reasoning.

## Scoring (`scoring.py` — deterministic)

The LLM proposes sub-scores; code clamps to range and sums:

| dimension | range |
|---|---|
| problem_severity | 0–25 |
| business_value | 0–25 |
| evidence_confidence | 0–20 |
| solution_fit | 0–20 |
| contactability | 0–10 |
| **total** | **0–100** |

Guard-rails: `evidence_confidence` is capped by a deterministic ceiling based on
evidence quantity + mean confidence (0 evidence → ≤4). If `is_opportunity` is
false, `problem_severity` is capped at 10. Individual scores + reasons are stored
in `evaluation_runs.score_breakdown`.

## Versioning & history

`evaluation_runs` stores `prompt_version`, `scoring_version`, `model`,
`llm_meta`. Re-evaluations create new rows — prior runs (and their pain
points / solutions) are never destroyed.
