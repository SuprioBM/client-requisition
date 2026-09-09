# Architecture

This document describes **implemented** behavior. Companion docs:
[discovery](discovery.md) · [research](research.md) · [evaluation](evaluation.md) ·
[outreach](outreach.md) · [database](database.md) · [error-handling](error-handling.md) ·
[deployment](deployment.md).

## Phases & separation of concerns

Three distinct responsibilities, never mixed:

| Phase | Job | Answers |
|---|---|---|
| **Discovery** | finds businesses | "who is out there?" |
| **Evaluation** | understands businesses | "is there a real, evidence-backed opportunity?" |
| **Outreach** | communicates the opportunity | "how do we start a conversation?" |

## Runtime topology

```
USER → FastAPI → Job row (Postgres) + enqueue (Redis list)
                      │
                      ▼
              Background worker  ──(claims job via DB lease)──►  LangGraph
                      │                                             │
          ┌───────────┴───────────┐                    ┌────────────┴───────────┐
          ▼                       ▼                    ▼                        ▼
   DISCOVERY GRAPH          EVALUATION GRAPH      checkpointer            structured logs
```

- **API never blocks** on discovery/research. It creates a `jobs` row and pushes the
  id to a Redis list, returning `{job_id, status: QUEUED}`.
- **Worker** does a reliable `BLMOVE` from `queue` → `processing`, claims the job with
  an atomic DB `UPDATE … WHERE status='QUEUED'` (lease + owner + expiry), runs the
  graph, then `ack`s. Stale leases (crashed workers) are detected and requeued.
- **Job state machine** (`app/db/models/enums.py::JOB_TRANSITIONS`) rejects illegal
  transitions (e.g. `COMPLETED → RUNNING`).

## Deterministic vs LLM

| Deterministic code | LLM (Groq) |
|---|---|
| API calls, URL/phone/domain normalization, HTTP status handling, dedup, DB ops, job state, retries, timeouts, provider selection, score arithmetic, schema validation | interpreting evidence, identifying candidate pain points, mapping problems → solutions, explaining value, opportunity reasoning, drafting outreach |

The LLM is only invoked **after** deterministic evidence collection, and every
structured output is validated with Pydantic (retry on invalid, bounded).

## Error taxonomy

`app/core/errors.py::ErrorCode` — a closed enum used internally everywhere and
mapped to safe `{success:false, error:{code,message}}` envelopes at the API edge.
`RETRYABLE_ERROR_CODES` / `NON_RETRYABLE_ERROR_CODES` drive the worker retry policy.

## Data quality

Records carry an origin (`RAW | NORMALIZED | VERIFIED | INFERRED`) and a kind
(`REAL | MOCK | TEST`). Provider facts and AI interpretations are stored separately
(`evidence` rows vs `pain_points` / `evaluation_runs`).

## Persistence model

See `docs/database.md`. Key tables: `jobs`, `prospects` (+ `prospect_sources`,
`prospect_contacts`), `research_runs` (+ `evidence`), `evaluation_runs`
(+ `pain_points`, `solutions`), `outreach_messages` (+ `outreach_events`),
`audit_events`.
