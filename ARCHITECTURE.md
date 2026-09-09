# Client Requisition Agent — End-to-End Architecture

This document describes **every process, connection and data flow** in the
system: the Next.js dashboard, the FastAPI backend, the background worker, the
LangGraph workflows, and every external service. It also covers how to run
everything and what you still need to set up.

> Companion docs: [`docs/discovery.md`](docs/discovery.md) ·
> [`docs/research.md`](docs/research.md) · [`docs/evaluation.md`](docs/evaluation.md) ·
> [`docs/outreach.md`](docs/outreach.md) · [`docs/database.md`](docs/database.md) ·
> [`docs/error-handling.md`](docs/error-handling.md) ·
> [`docs/deployment.md`](docs/deployment.md) · [`docs/frontend.md`](docs/frontend.md)

---

## 1. The one-paragraph version

You open the **Next.js dashboard** (`web/`, port 3000). Every request it makes
goes to a **same-origin proxy route** inside Next (`/api/backend/*`), which adds
the API key server-side and forwards to the **FastAPI backend** (port 8000). The
API is thin: for anything long-running it writes a `jobs` row to
**Postgres/SQLite**, pushes the id to **Redis** (or falls back to DB polling),
and returns `{job_id}`. A **background worker** (its own process, or embedded in
the API in dev) picks the job up, claims it with an atomic DB lease, and runs a
**LangGraph** workflow node-by-node. Discovery nodes call **Google Places /
DuckDuckGo / Brave**; evaluation nodes call **HTTPX / Playwright / Tavily** for
research and **Groq** (via LangChain) for the AI reasoning. After each node the
worker writes the current stage + partial results back onto the `jobs` row. The
dashboard's **job monitor** holds an **SSE** connection (`/jobs/{id}/stream`,
through the proxy) that re-emits that row ~1×/sec, and a React-Query cache that
gets invalidated on every stage change — so the operator watches the pipeline
run with no page refresh. Generated outreach lands as `PENDING_APPROVAL`; the
operator reviews/edits/approves in the UI; **sending is behind an interface** and
returns `NOT_CONFIGURED` (never a fake "SENT") unless SMTP is configured.

---

## 2. Process & port map

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ DEVELOPER MACHINE / SERVER                                                    │
│                                                                              │
│  ┌────────────────────┐        ┌──────────────────────────────┐              │
│  │ Next.js dashboard  │  HTTP  │ Next route handler (server)   │              │
│  │ (browser JS)       │ ─────► │ /api/backend/[...path]        │              │
│  │ localhost:3000     │ ◄───── │  + X-API-Key (BACKEND_API_KEY)│              │
│  └────────────────────┘  SSE   └───────────────┬──────────────┘              │
│                                                │ HTTP / SSE (BACKEND_URL)    │
│                                                ▼                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ FastAPI  (uvicorn, localhost:8000)   app.main:app                      │  │
│  │  - routers: health, dashboard, discovery, jobs, prospects,            │  │
│  │             research, evaluation, outreach                            │  │
│  │  - request-id middleware, CORS, exception handlers                    │  │
│  │  - lifespan: validate config → (dev) start embedded worker            │  │
│  └───────┬───────────────────────────────┬──────────────────────┬────────┘  │
│          │ SQLAlchemy async              │ redis.asyncio         │           │
│          ▼                               ▼                       │           │
│  ┌───────────────┐               ┌───────────────┐               │           │
│  │ Postgres /    │               │ Redis         │               │           │
│  │ Supabase      │               │ (job queue +  │               │           │
│  │ (or SQLite    │               │  cache;       │               │           │
│  │  in dev)      │               │  optional)    │               │           │
│  └───────▲───────┘               └───────▲───────┘               │           │
│          │ SQLAlchemy async              │ BLMOVE / RPUSH        │           │
│  ┌───────┴───────────────────────────────┴───────────────────────▼────────┐  │
│  │ Worker   `python -m app.workers.worker`  (or embedded task in API)     │  │
│  │  loop: dequeue → acquire_lease (DB) → run_job → heartbeat → ack        │  │
│  │  sweeper: requeue jobs with expired leases                            │  │
│  │  handlers: DISCOVERY / RESEARCH / EVALUATION  →  LangGraph             │  │
│  └───────┬──────────────────────────────────────────────────────────────┘  │
│          │                                                                  │
└──────────┼──────────────────────────────────────────────────────────────────┘
           │ HTTPS (outbound)
           ▼
   ┌─────────────────────────────────────────────────────────────────────┐
   │ Google Places API   · DuckDuckGo (ddgs)   · Brave Search API        │
   │ Google Geocoding API · target business websites (HTTPX / Playwright)│
   │ Tavily API           · Groq API (LLM)     · SMTP server (optional)  │
   └─────────────────────────────────────────────────────────────────────┘
```

| Process | Command | Port | Notes |
|---|---|---|---|
| Frontend | `cd web && npm run dev` | 3000 | Next 15; also hosts the server-side proxy route |
| Backend API | `uvicorn app.main:app` | 8000 | FastAPI; in `APP_ENV=development` it also runs the worker in-process |
| Worker | `python -m app.workers.worker` | — | separate process for production; unnecessary in dev |
| Postgres | docker / managed | 5432 | system of record; SQLite file used for local dev/tests |
| Redis | docker / managed | 6379 | job-queue signal + cache; **optional in dev** (DB-poll fallback) |

There is also a **static fallback UI** served by FastAPI at `GET /`
(`frontend/index.html`) — a zero-build single page. The real dashboard is `web/`.

---

## 3. The proxy boundary (frontend ↔ backend)

**File:** `web/src/app/api/backend/[...path]/route.ts`

Every call the browser makes hits `/api/backend/<backend-path>` on the **same
origin** as the page. The Next route handler:

1. Reads server-only env: `BACKEND_URL` (default `http://localhost:8000`),
   `BACKEND_API_KEY` (default empty).
2. Copies request headers (minus hop-by-hop), **adds `X-API-Key: <BACKEND_API_KEY>`**
   if set.
3. Forwards method + query + body to `${BACKEND_URL}/<path>`.
4. Returns `new Response(upstream.body, …)` — **streams the body unchanged**, so
   `text/event-stream` (SSE) passes straight through.
5. On a fetch failure returns `502 {success:false, error:{code:"BACKEND_UNREACHABLE"}}`.

Consequences:
- **No secret in client JS** — the API key lives only in the Next server process.
- **No browser CORS** — the browser only talks to its own origin. (The backend
  still sets `CORS_ORIGINS` for any *other* client that hits it directly.)
- The frontend API client (`web/src/lib/api/client.ts`) hard-codes
  `API_BASE = "/api/backend"` and always sends/parses the envelope
  `{success, data, error}`.

---

## 4. Response envelope & errors (backend → frontend)

Every backend response is wrapped:

```jsonc
// success
{ "success": true,  "data": { … },  "error": null }
// failure
{ "success": false, "data": null,   "error": { "code": "PROVIDER_TIMEOUT", "message": "…", "context": {…} } }
```

- Backend: `app/schemas/common.py::ok()/err()`, exception handlers in
  `app/api/errors.py`, closed error taxonomy in `app/core/errors.py::ErrorCode`.
- Every response carries an `X-Request-ID` header (generated by middleware in
  `app/main.py`) that is also bound to every structured log line for that request.
- Frontend: `apiFetch()` unwraps `data` on success and **throws `ApiError`**
  (with `.code`, `.status`) on failure. `QueryBoundary`
  (`web/src/components/shared/states.tsx`) turns that into a visible
  loading / error / empty / content state — never a blank screen, never a
  swallowed error.

---

## 5. Data model (Postgres / SQLite)

13 tables, created by Alembic (`alembic upgrade head`). Portable between
Postgres and SQLite (generic `JSON`, string PKs, no PG-only types).

```
jobs ─────────────────────────────────────────────────────────────────────────
  id, job_type(DISCOVERY|RESEARCH|EVALUATION), status(state machine),
  params(JSON), current_stage, progress(JSON ← live pipeline state),
  result(JSON), warnings(JSON), error_code, error_message,
  retry_count/max_retries, lease_owner/lease_expires_at/heartbeat_at,
  prospect_id (for RESEARCH/EVALUATION), started_at/completed_at

prospects ────────────────────────────────────────────────────────────────────
  id, business_name, normalized_name, industry, country, city, address,
  lat/lng, phone/phone_e164, email, website, canonical_domain, google_place_id,
  rating, review_count,
  status (DISCOVERED→RESEARCHING→RESEARCHED→EVALUATING→EVALUATED→
          OUTREACH_DRAFTED→OUTREACH_APPROVED→CONTACTED / REJECTED / ARCHIVED),
  quality_status (OK|REVIEW|REJECTED), record_kind (REAL|MOCK|TEST),
  provider_metadata(JSON), discovery_job_id,
  last_researched_at / last_evaluated_at / last_contacted_at
   │
   ├─< prospect_sources   (provenance: provider, source_identity, source_url,
   │                        search_query, raw_payload(JSON), collected_at)
   │                        UNIQUE(prospect_id, provider, source_identity)
   └─< prospect_contacts   (channel, value, data_origin, source_url, verified)

research_runs ────────────────────────────────────────────────────────────────
  id, prospect_id, job_id, schema_version, status(RUNNING|COMPLETED|PARTIAL|FAILED),
  sources_used(JSON), website_status, website_final_url, signals(JSON),
  social_profiles(JSON), content_hash, error_code/error_message,
  started_at/completed_at
   └─< evidence   (evidence_type, source_type, source_url, extracted_text,
                   observation, confidence 0..1, data_origin
                   (RAW|NORMALIZED|VERIFIED|INFERRED), extra(JSON), collected_at)

evaluation_runs ──────────────────────────────────────────────────────────────
  id, prospect_id, research_run_id, job_id, prompt_version, scoring_version,
  model, status, opportunity_summary, commercial_potential, opportunity_reasoning,
  is_opportunity,
  score_problem_severity / business_value / evidence_confidence / solution_fit /
  contactability / score_total, score_breakdown(JSON), llm_meta(JSON), completed_at
   ├─< pain_points  (category, title, description, confidence
   │                 (CONFIRMED|LIKELY|POSSIBLE|NOT_ENOUGH_EVIDENCE),
   │                 evidence_ids(JSON) ← references evidence.id, severity)
   └─< solutions    (service_category, service_name, why_it_fits, expected_value,
                     confidence, fit_rank, pain_point_id)

outreach_messages ────────────────────────────────────────────────────────────
  id, prospect_id, evaluation_run_id, channel(EMAIL|WHATSAPP),
  status (DRAFTED|PENDING_APPROVAL|APPROVED|REJECTED|SENT|NOT_CONFIGURED|
          BLOCKED_DUPLICATE),
  strategy(JSON), subject, body, edited_body, to_address, prompt_version,
  llm_meta(JSON), evidence_ids(JSON), approved_at/approved_by, rejected_reason,
  sent_at/send_provider/send_reference,
  follow_up_count, next_follow_up_at, reply_status
   └─< outreach_events   (append-only lifecycle: drafted/edited/approved/
                          rejected/sent/delivered/opened/replied/
                          follow_up_due/follow_up_sent/closed)

audit_events ─────────────────────────────────────────────────────────────────
  append-only: entity_type, entity_id, action, actor, detail(JSON)
```

**Separation of concerns in the data:** provider facts (`evidence`,
`prospects.rating`) live apart from AI interpretation (`pain_points`,
`evaluation_runs`). `data_origin` marks `VERIFIED` observation vs `INFERRED`.

---

## 6. Job lifecycle & the queue

### 6.1 Creating a job

`app/services/job_service.py::create_and_enqueue()`

```
API route (e.g. POST /api/v1/discovery/search)
  → JobRepository.create(job_type, params)      # INSERT jobs row, status=QUEUED
  → session.commit()
  → queue.enqueue(job.id)                        # RPUSH id onto Redis list
                                                 #  (or no-op for DB-poll backend)
  → return { job_id, status: "QUEUED" }
```

### 6.2 The queue backend (`app/workers/queue.py`)

`get_queue()` selects once per process:

| Condition | Backend | Behaviour |
|---|---|---|
| Redis reachable | `RedisQueue` | `enqueue` = `RPUSH`; `dequeue` = `BLMOVE queue → processing` (reliable handoff); `ack` = `LREM processing`; `requeue_stuck` on worker start moves stranded `processing` ids back |
| Redis down **and** `APP_ENV != production` | `DbQueue` | `enqueue` = no-op (row already `QUEUED`); `dequeue` = `SELECT id FROM jobs WHERE status='QUEUED' ORDER BY created_at LIMIT 1` (0.5 s poll) |
| Redis down **and** `APP_ENV = production` | — | hard fail (`RedisError`) |

Job **state** is always in Postgres; Redis only carries the "work exists" signal.

### 6.3 The worker loop (`app/workers/worker.py`)

```
main():
  configure_logging → validate_runtime → register_handlers
  queue.requeue_stuck()                       # recover crashed-worker leftovers
  start _sweeper task                         # every ~lease/2s: find_stale() → requeue
  loop while not shutdown:
    job_id = queue.dequeue(timeout=5)
    _process_one(job_id):
      claimed = JobRepository.acquire_lease(job_id, WORKER_ID, lease_seconds)
        # atomic:  UPDATE jobs SET status='RUNNING', lease_owner=?, lease_expires_at=?
        #          WHERE id=? AND status='QUEUED'      → rowcount 0 means someone else got it
      if not claimed: ack + skip
      start _heartbeat task                   # every lease/3s: extend lease_expires_at
      run_job(job_id)                         # dispatch + retry policy
      cancel heartbeat, queue.ack(job_id)
```

Two workers can run safely: the atomic `acquire_lease` UPDATE is the real claim.
Signal handlers (`SIGINT`/`SIGTERM`) set a shutdown event so the in-flight job
finishes before exit.

### 6.4 Dispatch & retry (`app/workers/jobs.py::run_job`)

```
run_job(job_id):
  load job; if QUEUED → transition to RUNNING (safety net for direct calls)
  fn = _HANDLERS[job.job_type]                # @handler(JobType.X) registry
  try: await fn(job_id)
  except AppError as e:  _handle_failure(code=e.code, retryable=is_retryable(e.code))
  except Exception:     _handle_failure(code=INTERNAL_ERROR, retryable=True)

_handle_failure:
  if retryable and retry_count < max_retries:
     store error_code/message, JobRepository.prepare_retry (retry_count++, status→QUEUED)
     sleep(min(MAX_RETRY_DELAY, RETRY_BASE_DELAY * 2**retry_count))     # exp backoff
     queue.enqueue(job_id)
  else:
     JobRepository.mark_failed → status=FAILED
     print CONFIGURATION/JOB-FAILED terminal banner  (app/core/banners.py)
```

Retryable vs not is defined in `app/core/errors.py`
(`RETRYABLE_ERROR_CODES` / `NON_RETRYABLE_ERROR_CODES`). Never retried: config
errors, auth failures, quota exceeded, `LOCATION_INVALID`, `WEBSITE_SSRF_BLOCKED`,
validation errors.

### 6.5 Job state machine (`app/db/models/enums.py::JOB_TRANSITIONS`)

```
QUEUED  → RUNNING | CANCELLED | FAILED
RUNNING → COMPLETED | COMPLETED_WITH_WARNINGS | FAILED | CANCELLED | QUEUED(requeue)
FAILED  → QUEUED (explicit retry)
COMPLETED / COMPLETED_WITH_WARNINGS / CANCELLED → (terminal)
```

`JobRepository.transition()` rejects any transition not in this map with
`JOB_INVALID_STATE`.

---

## 7. Discovery — full data flow

**Trigger:** dashboard Discover form → `POST /api/v1/discovery/search`
(`{country, city, industry, radius_km, target_leads}`), guarded by
`require_api_key`.

```
FRONTEND                     BACKEND API              WORKER + LANGGRAPH               EXTERNAL
────────                     ───────────              ─────────────────               ────────
DiscoveryForm.onSubmit
  zod validate
  useStartDiscovery ──POST /discovery/search──►
                             create_and_enqueue
                             INSERT jobs(DISCOVERY,QUEUED)
                             RPUSH id → Redis
                       ◄──── { job_id, "QUEUED" }
  router.push(/jobs/{id})
  ── open SSE /jobs/{id}/stream ─────────────────────────────────────────────────►
                                                     worker.dequeue → acquire_lease
                                                     run_discovery_job(job_id):
                                                       checkpointer_scope() (sqlite/pg/memory)
                                                       graph = build_discovery_graph(cp)
                                                       async for state in graph.astream(...):
                             ◄── after each node: _persist_progress(job_id, state)
                                 UPDATE jobs SET current_stage=?, progress=? (+provider_runs, counters)
     SSE re-emits jobs row 1×/sec  ◄───────────────────────────────────────────────
     use-job-stream: setQueryData(job) + invalidate prospects/stats/activity

  Graph nodes (app/graphs/discovery_graph.py):
   validate_search        require industry/city/country
   resolve_location       resolve_location(city,country):
                            Google Geocoding API ───────────────────────────────► Google Geocoding
                            └ ZERO_RESULTS→LOCATION_INVALID(400)
                            └ >1 locality→LOCATION_AMBIGUOUS(400)
                            └ REQUEST_DENIED/quota → fall back to offline gazetteer
                            └ no key → offline gazetteer → else 400
   plan_queries           planner.py: industry synonyms + generic, capped MAX_QUERIES_PER_PLAN
   google_discovery       GooglePlacesProvider.search per place-query (concurrent) ─► Places API (New) searchText
   duckduckgo_discovery   DuckDuckGoProvider.search per web-query (ddgs, threadpool) ─► DuckDuckGo/Bing
   brave_discovery        BraveProvider.search (skipped if no BRAVE_SEARCH_API_KEY) ─► Brave Search API
      each provider returns a ProviderRun{status, error_code, candidates[], duration_ms}
      provider errors are mapped to ErrorCode, appended, NEVER abort the graph
   aggregate              any_provider_succeeded? collect warnings
   normalize              normalizer.py: canonical domain (offline tldextract),
                          website scheme/host, keep raw address
   clean                  cleaner.py: drop empty/non-business/"Top 10…"/no-signal;
                          uncertain web-only hits → flagged REVIEW (never deleted)
   deduplicate            deduplicator.py: union-find over strong signals
                          (google_place_id | canonical domain | phone E.164),
                          then bounded fuzzy name+address.  BRANCH PROTECTION:
                          different address / place id / "- <area>" name → never merge
   save                   ProspectRepository.upsert_from_cluster (idempotent):
                            match existing by place_id → domain → phone → (name+city+addr)
                            fill only-missing fields (never overwrite)
                            de-dupe prospect_sources on (provider, source_identity)
                            INSERT/UPDATE prospects (+ sources + contacts)   ──► Postgres
                          build summary{raw_candidates, unique_clusters,
                                        prospects_created/updated, prospect_ids, warnings}

  run_discovery_job finish:
    if no provider succeeded AND nothing saved → raise PROVIDER_UNAVAILABLE
       ("discovery_providers_unavailable") → retry/fail
    else UPDATE jobs result=summary, status = COMPLETED_WITH_WARNINGS if warnings else COMPLETED

  SSE emits final `done` event  ──────────────────────────────────────────────►
  use-job-stream invalidates jobs/prospects/outreach/stats
  UI: job monitor shows COMPLETED + result; /prospects table now populated
```

**Provider abstraction:** all providers implement
`app/discovery/base.py::BusinessDiscoveryProvider`. `app/discovery/registry.py`
is the only place that decides which concrete providers exist; tests inject mocks
via `set_provider_factory`.

---

## 8. Research — full data flow

Research runs **standalone** (`POST /api/v1/prospects/{id}/research` → RESEARCH
job) **and** as the `research_business` node inside the evaluation graph. Core:
`app/research/orchestrator.py::research_prospect(prospect_dict)`.

```
research_prospect:
  website known?
   ├─ YES → http_client.fetch(url)                         ──► target website (HTTPX)
   │        · validate_public_url() on the URL AND every redirect hop:
   │          block localhost / private / link-local / reserved IPs / cloud metadata
   │          (169.254.169.254). Disabled only if ALLOW_PRIVATE_NETWORK_RESEARCH=true.
   │        · hard timeout (RESEARCH_HTTP_TIMEOUT_SECONDS), size cap
   │          (RESEARCH_MAX_RESPONSE_BYTES), HTML/plain content-type only
   │        · returns FetchResult{status: ACTIVE|REDIRECTED|NOT_FOUND|TIMEOUT|
   │          FORBIDDEN|SERVER_ERROR|INVALID|UNKNOWN}
   │        usable HTML?
   │          ├─ parser.py (BeautifulSoup): title, meta, headings, nav, links,
   │          │   forms, CTA keywords, booking/ordering links, social profiles,
   │          │   tech fingerprints (WordPress/Shopify/React/livechat…)
   │          ├─ if looks JS-rendered (thin text + SPA markers) AND
   │          │   PLAYWRIGHT_ENABLED → playwright_client.render() ──► headless Chromium
   │          ├─ extractor.py (Trafilatura): clean main-content text (≤12k chars)
   │          └─ follow ≤2 key internal pages (contact/book/services/…)
   │
   └─ NO / fetch failed / thin → DuckDuckGo + Brave search for "<name> <city>"  ──► DDG / Brave
                                 to discover the official site / socials
                                 still thin AND TAVILY_API_KEY set → tavily.search()  ──► Tavily API

  signals.py  → deterministic WebsiteSignals + BusinessSignals + online_presence
                (has_booking_mechanism, has_primary_cta, is_https, has_viewport_meta,
                 service_pages_found, social_profiles, technology_signals,
                 total_text_length, rating, review_count, public contact channels …)
  evidence.py → Evidence[]: each an objective, hedged observation
                ("No online appointment mechanism was identified on the researched pages")
                with source_type, source_url, confidence (calibrated per signal),
                data_origin (VERIFIED direct / INFERRED fingerprint/snippet)

persist (app/db/repositories/research.py):
  INSERT research_runs (+ evidence children)                ──► Postgres
  UPDATE prospects.last_researched_at, website (if discovered), status→RESEARCHED
```

**Cache:** `research_service.run_research()` returns a prior `research_runs` row
if one completed within `RESEARCH_CACHE_TTL_SECONDS` (7 days) unless `force=true`.
Raw HTML is never sent to the LLM — only the compact `evidence` list + trimmed
`signals`.

---

## 9. Evaluation — full data flow

**Trigger:** `POST /api/v1/prospects/{id}/evaluate` → EVALUATION job →
`app/workers/evaluation_handler.py` → `graph.astream(build_evaluation_graph())`
(same SSE progress mechanism as discovery, stages in `EVALUATION_STAGES`).

```
Graph nodes (app/graphs/evaluation_graph.py):

 load_prospect             prospect dict from DB; status→EVALUATING
 research_business          run_research(prospect_id)  (§8; uses cache)
 collect_evidence           load evidence rows for the research_run → state["evidence"]
                            (each carries its DB id — the AI cites these ids)
 detect_pain_points ───────► Groq  (steps.detect_pain_points → LLM)
 map_solutions      ───────► Groq  (only pain points with a credible service fit)
 evaluate_opportunity ─────► Groq  (is_opportunity, commercial_potential
                                    LOW|MEDIUM|HIGH|UNKNOWN, contactable, worthwhile)
 score_lead         ───────► Groq  (proposes 5 sub-scores) THEN
                            compute_score() — DETERMINISTIC: clamp each dimension,
                            cap evidence_confidence by an evidence-strength ceiling
                            (0 evidence → ≤4), cap problem_severity ≤10 if not an
                            opportunity, sum → total 0..100
 finalize_evaluation        INSERT evaluation_runs (+ pain_points + solutions)  ──► Postgres
                            UPDATE prospects.last_evaluated_at, status→EVALUATED

 ── conditional edge ──  is_opportunity AND outreach_worthwhile ?
        no  → END
        yes ↓
 generate_outreach_strategy ─► Groq  (primary observation/problem/solution/value/
                                      tone/CTA/evidence_ids — focus on the single
                                      strongest legitimate opportunity)
 generate_email             ─► Groq  (personal opening → evidence-backed observation
                                      → problem → solution → realistic value → soft CTA;
                                      NO evidence ids / placeholders in the body)
 generate_whatsapp          ─► Groq  (short, not a copy of the email)
 persist_outreach           OutreachRepository.create per channel, status=PENDING_APPROVAL
                            duplicate check: recent_message(prospect, channel) within 30d
                            → BLOCKED (records "duplicate outreach blocked")
                            status→OUTREACH_DRAFTED
 human_approval             approval_status = "PENDING_APPROVAL"  (terminal; real
                            approve/send happens via the API later)
```

### 9.1 The LLM client (`app/evaluation/llm.py`)

```
LLMClient.structured(label, PydanticSchema, prompt):
  backend = _RealGroq  →  langchain_groq.ChatGroq(model=GROQ_MODEL,
                          response_format={"type":"json_object"}, temperature=0.2)
  loop (≤2 attempts):
    raw, meta = backend.complete_json(EVALUATOR_SYSTEM, prompt)   ──► Groq API
    on 429  → sleep(parsed "try again in Xs", ≤8 times) and retry
    on other error → map to ErrorCode (LLM_TIMEOUT / LLM_RATE_LIMITED /
                     LLM_AUTH_FAILED / LLM_UNAVAILABLE) and raise LLMError
    parse JSON, validate against the schema
      valid   → return (model, obs{model, tokens, latency_ms, attempts, status})
      invalid → retry once with a constrained prompt ("return ONLY JSON with keys […]")
    still invalid → raise LLMError(LLM_INVALID_OUTPUT)
```

`EVALUATOR_SYSTEM` is the hallucination guard: *use only supplied evidence, cite
evidence ids, `NOT_ENOUGH_EVIDENCE` when unsupported, never fabricate
processes / tech / budgets / willingness to pay, prefer conservative
conclusions.* Prompts are versioned (`PROMPT_VERSION`, `SCORING_VERSION` stored
on every `evaluation_runs` row). Tests inject a `FakeLLMClient` via
`set_llm_client` — **zero network**.

### 9.2 Deterministic vs LLM

| Deterministic code | LLM (Groq) |
|---|---|
| API calls, URL/phone/domain normalisation, HTTP status handling, dedup, DB ops, job state, retries, timeouts, provider selection, **score arithmetic**, schema validation | interpreting evidence, identifying candidate pain points, mapping problems → solutions, explaining value, opportunity reasoning, drafting outreach copy |

---

## 10. Outreach approval & sending

```
Operator opens /outreach/[id]  (OutreachReview component)
  GET /api/v1/outreach/{id}  → message + strategy + events

Edit  → PATCH /api/v1/outreach/{id} {subject?, body?}
        stores edited_body (NEVER overwrites the original body); logs "edited"

Approve → confirm dialog → POST /api/v1/outreach/{id}/approve {edited_body?}
          status PENDING_APPROVAL → APPROVED; prospect → OUTREACH_APPROVED
          writes outreach_events + audit_events

Reject  → POST /api/v1/outreach/{id}/reject {reason?}  → status REJECTED

Send    → POST /api/v1/outreach/{id}/send   (only if status == APPROVED)
          duplicate guard: another SENT message, same channel, ≤30d → DUPLICATE_OUTREACH (409)
          provider = get_outreach_provider(channel):
            EMAIL + SMTP_HOST/PORT/FROM set → SmtpEmailProvider  ──► SMTP server
            else                            → NullOutreachProvider
          result.ok  → status SENT, sent_at, next_follow_up_at = now + OUTREACH_FOLLOW_UP_DAYS
          NOT ok     → status NOT_CONFIGURED  ← never a fake "SENT"

Follow-up: outreach_service.process_followups() (call on a schedule) marks due
  follow-ups (event follow_up_due), enforces OUTREACH_MAX_FOLLOW_UPS, stops once
  a reply is recorded. Follow-ups are NOT auto-sent.
```

No autonomous outreach anywhere in V1: AI drafts → human reviews → human
approves → human sends.

---

## 11. Real-time: how the UI stays live without refresh

### 11.1 SSE (job monitor only)

- **Backend:** `GET /api/v1/jobs/{id}/stream` (`app/api/routes/jobs.py`) —
  `sse-starlette` `EventSourceResponse`. Every ~1 s it reads the single `jobs`
  row (indexed PK), and if the serialised payload changed emits
  `event: job\ndata: <JobOut json>`. On a terminal status it emits
  `event: done` and closes. Disconnect-aware.
- **Backend writes the live state:** the discovery/evaluation handlers use
  `graph.astream(...)` and call `_persist_progress(job_id, state)` after every
  node — writing `current_stage`, `progress.percent`, `progress.provider_runs`,
  `progress.counters` onto the row. So the SSE payload carries real per-stage
  data, not just "RUNNING".
- **Frontend:** `web/src/lib/realtime/use-job-stream.ts` opens
  `EventSource('/api/backend/api/v1/jobs/{id}/stream')` (through the proxy). On
  each `job` event it `queryClient.setQueryData(['job', id], job)` and, when the
  stage changed, invalidates `['prospects']`, `stats`, `['activity']`, and the
  subject prospect's `profile`/`research`/`evaluation`/`outreach`. On terminal
  status it also invalidates the job/outreach lists.
- Fallback: `useJob(id, {poll:true})` polls the same row every 2 s while
  non-terminal, so the monitor works even if SSE fails (proxy hiccup, etc.).

### 11.2 Adaptive polling (everywhere else)

`web/src/lib/query/hooks.ts` — TanStack Query `refetchInterval`:

| Query | Interval |
|---|---|
| `useHealth` (status bar) | 15 s |
| `useStats` (KPIs, sidebar badges) | 10 s |
| `useActivity` (feed) | 8 s |
| `useJobs` (jobs list) | 3 s while any job is active, else 15 s |
| `useActiveJobs` (dashboard) | 2.5 s while jobs exist, else 8 s |
| `useOutreachList` | 12 s |
| prospect detail / research / evaluation | not polled — invalidated by the job stream |

Mutations (`useStartDiscovery`, `useApproveOutreach`, …) invalidate the exact
affected query keys on success and raise a `sonner` toast.

---

## 12. Every external connection

| # | From | To | Protocol | When | Auth | Failure handling |
|---|---|---|---|---|---|---|
| 1 | browser | Next proxy `/api/backend/*` | HTTP/SSE, same origin | every API call | none (same origin) | `502 BACKEND_UNREACHABLE` → `ErrorPanel` + Retry |
| 2 | Next proxy (server) | FastAPI `BACKEND_URL` | HTTP/SSE | forwards #1 | `X-API-Key: BACKEND_API_KEY` | fetch throws → 502 envelope |
| 3 | FastAPI | Postgres/SQLite (`DATABASE_URL`) | SQLAlchemy async (asyncpg / aiosqlite) | all persistence | connection string | `DATABASE_ERROR` (retryable) |
| 4 | FastAPI + Worker | Redis (`REDIS_URL`) | `redis.asyncio` | queue signal + cache | URL | dev → DB-poll fallback; prod → hard fail |
| 5 | Worker (discovery) | Google Places API (New) | HTTPS `POST places:searchText` | `google_discovery` node | `X-Goog-Api-Key: GOOGLE_MAPS_API_KEY` | quota→`PROVIDER_QUOTA_EXCEEDED`, 403/billing→`PROVIDER_AUTH_FAILED`, 429→`PROVIDER_RATE_LIMITED`, timeout→`PROVIDER_TIMEOUT`; graph continues on other providers |
| 6 | Worker | Google Geocoding API | HTTPS GET | `resolve_location` node | `GOOGLE_MAPS_API_KEY` | `REQUEST_DENIED`/quota → offline gazetteer; ZERO_RESULTS → `LOCATION_INVALID` 400 |
| 7 | Worker | DuckDuckGo (via `ddgs`) | HTTPS (scrapes Bing/DDG) | `duckduckgo_discovery`, research fallback | none | classify rate/timeout; non-fatal (often returns 0 — Google is primary) |
| 8 | Worker | Brave Search API | HTTPS GET | `brave_discovery`, research fallback | `X-Subscription-Token: BRAVE_SEARCH_API_KEY` | skipped cleanly if no key; standard HTTP mapping |
| 9 | Worker | target business websites | HTTPS/HTTP GET (HTTPX) | research | `RESEARCH_USER_AGENT` | SSRF guard; timeout/size caps; classified `WebsiteStatus`; PARTIAL run, never crash |
| 10 | Worker | headless Chromium (Playwright) | local subprocess | research, only for JS-heavy sites when `PLAYWRIGHT_ENABLED` | — | `PLAYWRIGHT_FAILED` → continue with HTTP result |
| 11 | Worker | Tavily API | HTTPS (`tavily-python`, threadpool) | research last-resort fallback | `TAVILY_API_KEY` | disabled if no key; errors classified, non-fatal |
| 12 | Worker | Groq API | HTTPS (`langchain-groq` → `groq`) | every evaluation/outreach LLM step | `GROQ_API_KEY`, model `GROQ_MODEL` | 429 → backoff & retry (≤8); other → `LLM_*` ErrorCode; invalid JSON → 1 constrained retry then `LLM_INVALID_OUTPUT` |
| 13 | Backend | SMTP server | SMTP(+STARTTLS) | `outreach send`, only if `SMTP_*` set | `SMTP_USER`/`SMTP_PASSWORD` | not configured / any error → `NOT_CONFIGURED` (never fake SENT) |

All outbound provider keys live **only** in the backend `.env`. The browser
never receives any of them.

---

## 13. Configuration

### 13.1 Backend — `.env` (`app/core/config.py::Settings`)

| Var | Required | Purpose |
|---|---|---|
| `APP_ENV` | — | `development` \| `testing` \| `production` (default `development`) |
| `DATABASE_URL` | **yes** | async driver: `postgresql+asyncpg://…` or `sqlite+aiosqlite:///./requisition.db` |
| `REDIS_URL` | **yes** | job queue + cache. Unreachable in dev → DB-poll fallback; required in prod |
| `API_KEY` | prod only | guards mutating/outreach endpoints via `X-API-Key`. Empty in dev = auth disabled |
| `CORS_ORIGINS` | — | comma list; only enforced when `APP_ENV=production` (proxy makes it moot for the dashboard) |
| `GOOGLE_MAPS_API_KEY` | feature | primary discovery + geocoding. Absent → DDG/Brave only + gazetteer |
| `BRAVE_SEARCH_API_KEY` | feature | secondary discovery / website discovery |
| `TAVILY_API_KEY` | feature | selective research fallback |
| `GROQ_API_KEY` / `GROQ_MODEL` | feature | LLM. Default model `openai/gpt-oss-120b` |
| `PLAYWRIGHT_ENABLED` / `PLAYWRIGHT_HEADLESS` | — | JS-render fallback |
| `RESEARCH_HTTP_TIMEOUT_SECONDS` / `RESEARCH_MAX_RESPONSE_BYTES` / `RESEARCH_CACHE_TTL_SECONDS` / `RESEARCH_USER_AGENT` | — | research knobs |
| `ALLOW_PRIVATE_NETWORK_RESEARCH` | — | SSRF guard toggle — keep `false` |
| `DISCOVERY_PROVIDER_CONCURRENCY` / `RESEARCH_CONCURRENCY` / `MAX_QUERIES_PER_PLAN` | — | cost / concurrency |
| `WORKER_JOB_LEASE_SECONDS` / `RETRY_BASE_DELAY_SECONDS` / `MAX_RETRY_DELAY_SECONDS` | — | worker timing |
| `RUN_EMBEDDED_WORKER` | — | unset → worker runs in the API process when `APP_ENV=development` |
| `LANGGRAPH_CHECKPOINT_DB` | — | empty → local sqlite checkpoint file; or a `postgresql://` URL for multi-worker |
| `OUTREACH_SENDER_NAME` / `OUTREACH_FOLLOW_UP_DAYS` / `OUTREACH_MAX_FOLLOW_UPS` | — | outreach |
| `SMTP_HOST/PORT/FROM/USER/PASSWORD/STARTTLS` | optional | real email sending |
| `SERVICES_KB_PATH` | optional | JSON file overriding the service catalogue |

> The loader defensively strips inline `# comments` from `.env` values
> (`_strip_inline_comments`), because pydantic-settings does not.

### 13.2 Frontend — `web/.env.local`

| Var | Scope | Purpose |
|---|---|---|
| `BACKEND_URL` | **server-only** | where the Next proxy forwards (default `http://localhost:8000`) |
| `BACKEND_API_KEY` | **server-only** | injected as `X-API-Key` by the proxy; set to match backend `API_KEY` in production |
| `NEXT_PUBLIC_SSE_BASE` | public (optional) | if set, the browser's `EventSource` connects the job stream **directly** to this backend origin instead of through the proxy — needed on platforms whose serverless functions time out mid-stream (Vercel). The stream endpoint is an unauthenticated GET, so no secret is exposed; the backend must list the dashboard origin in `CORS_ORIGINS`. |

No provider/LLM keys ever go in the frontend.

---

## 14. Startup sequence

```
1. alembic upgrade head                 # schema
2. uvicorn app.main:app
     lifespan:
       configure_logging()
       validate_runtime()               # missing DATABASE_URL/REDIS_URL (or API_KEY in prod)
                                         #   → prints CONFIGURATION ERROR banner, exits 1
       log capability summary           # which providers/LLM are enabled
       if APP_ENV=development: embedded worker task starts (worker.main in-process)
3. (production) python -m app.workers.worker   # separate process instead of embedded
4. cd web && npm run dev
     Next serves the dashboard on :3000 and the proxy route
     browser → GET / → dashboard → GET /api/backend/api/v1/dashboard/health → proxy → backend
```

`GET /health` = liveness; `GET /health/ready` and `GET /api/v1/dashboard/health`
report DB + Redis + capability status (the dashboard status bar).

---

## 15. How to run

### 15.1 Local, zero infra (SQLite + DB-poll queue) — fastest

```bash
# --- backend ---
python -m venv .venv
.venv\Scripts\activate                       # Windows;  source .venv/bin/activate elsewhere
pip install -r requirements-dev.txt
playwright install chromium                   # needed for JS-heavy site research

cp .env.example .env
#   edit .env:
#     APP_ENV=development
#     DATABASE_URL=sqlite+aiosqlite:///./requisition.db
#     REDIS_URL=redis://localhost:6379/0      # fine if Redis is not running (DB-poll fallback)
#     GROQ_API_KEY=...        GROQ_MODEL=openai/gpt-oss-120b
#     GOOGLE_MAPS_API_KEY=...                 # optional; without it, DDG/Brave + gazetteer
#     TAVILY_API_KEY=...                      # optional
alembic upgrade head
uvicorn app.main:app --reload                 # :8000  (+ embedded worker)

# --- frontend (second terminal) ---
cd web
npm install
cp .env.example .env.local                    # BACKEND_URL=http://localhost:8000 ; BACKEND_API_KEY=
npm run dev                                    # http://localhost:3000
```

Open **http://localhost:3000**, go to **Discover**, submit
`Bangladesh / Dhaka / dental / 10 / 10`, watch the job monitor.

### 15.2 Docker (Postgres + Redis + API + Worker)

```bash
cp .env.example .env          # fill provider keys
docker compose up --build
# API on :8000 (runs `alembic upgrade head` first), worker as its own service.
# Run the frontend separately:  cd web && npm run dev   (BACKEND_URL=http://localhost:8000)
```

### 15.3 Production shape

```
[Next.js (Vercel)]  →  [FastAPI web service]  →  [managed Postgres]
                              │                  [managed Redis]
                        [1..N Worker processes]  (python -m app.workers.worker)
```

- `APP_ENV=production`, set `API_KEY` (backend) and the matching
  `BACKEND_API_KEY` (frontend), set real `DATABASE_URL` + `REDIS_URL`,
  set `CORS_ORIGINS` to the dashboard origin, `RUN_EMBEDDED_WORKER=false`.
- On Vercel also set `NEXT_PUBLIC_SSE_BASE` to the backend origin (see § 13.2).
- For multiple workers set `LANGGRAPH_CHECKPOINT_DB` to a `postgresql://` URL.

**Deploy to Vercel + Render:** the repo ships **`render.yaml`** (a Render
Blueprint provisioning API + worker + Postgres + Redis). The full step-by-step —
Render Blueprint setup, Vercel project config, the SSE/serverless-timeout
handling, free-tier caveats, and a post-deploy smoke test — is in
[`docs/deployment.md`](docs/deployment.md#deploy-vercel-frontend--render-backend).

### 15.4 Tests / checks

```bash
# backend
pytest -q            # 92 tests, zero paid services (sqlite + fakeredis + respx + fake LLM)
ruff check app
mypy app

# frontend (in web/)
npm run test         # 14 vitest unit tests
npm run e2e          # 2 Playwright flows (own dev server on :3100, mocked backend)
npm run typecheck
npm run build

# real end-to-end against your live keys (costs a few API calls)
python scripts/run_e2e.py --industry dentist --city Dhaka --country Bangladesh
```

---

## 16. What you still need to do

1. **Provide at least one discovery key.** `GOOGLE_MAPS_API_KEY` is the reliable
   primary. Without any key, discovery falls back to DuckDuckGo (flaky, often 0
   results) + Brave (needs its own key). Get the Places API key from
   <https://console.cloud.google.com> → enable **Places API (New)** and
   **Geocoding API** and **enable billing** (geocoding refuses without it; the
   code then falls back to a small offline gazetteer of major cities).

2. **Provide `GROQ_API_KEY`** for evaluation/outreach. Your account currently
   has `openai/gpt-oss-*`, `qwen/*`, `groq/compound` (not Llama) — the default
   `GROQ_MODEL=openai/gpt-oss-120b` works. The **free tier is 8k tokens/min**;
   a full evaluation is 7 LLM calls and the client paces itself with 429
   backoff, so it can take ~1–2 minutes. A paid tier removes this.

3. **Choose a database.** For real use, point `DATABASE_URL` at Postgres or your
   Supabase project's Postgres connection string
   (`postgresql+asyncpg://postgres:<db-password>@db.<ref>.supabase.co:5432/postgres`
   — the DB password, not the `service_role` API key). Then `alembic upgrade head`.
   SQLite is fine for local dev only.

4. **Run Redis for production** (`docker compose up redis`, or a managed
   instance). In dev you can skip it — the queue falls back to polling the
   `jobs` table.

5. **Set the API key pair for any non-local deployment:** backend `API_KEY` +
   frontend `BACKEND_API_KEY` (same value). In `APP_ENV=production` a missing
   `API_KEY` fails startup.

6. **(Optional) real email sending:** set `SMTP_HOST/PORT/FROM` (and
   `SMTP_USER/PASSWORD`). Until then, "Send" reports `NOT_CONFIGURED` — the
   drafts and approval workflow still work fully. WhatsApp sending is not
   implemented in V1.

7. **(Optional) `playwright install chromium`** on the machine that runs the
   worker if you want JS-rendered-site research; the Docker image does this.

8. **Nothing else in code.** All pipeline logic, the dashboard, migrations,
   tests, Docker and docs are in place and committed.

---

## 17. Key source files (map)

```
BACKEND
  app/main.py                       FastAPI app, lifespan, CORS, request-id, static / route
  app/api/routes/*.py               endpoint handlers (thin)
  app/api/errors.py                 exception → envelope handlers
  app/core/{config,errors,exceptions,logging,security,http,redis,banners}.py
  app/db/models/*.py                13 tables + enums + JOB_TRANSITIONS
  app/db/repositories/*.py          all SQL lives here
  app/db/session.py                 async engine / session_scope
  app/workers/queue.py              RedisQueue | DbQueue backend selection
  app/workers/worker.py             worker loop, lease, heartbeat, sweeper
  app/workers/jobs.py               dispatch registry + retry policy
  app/workers/{discovery,research,evaluation}_handler.py   graph.astream + progress persist
  app/workers/embedded.py           run the worker inside the API (dev)
  app/graphs/discovery_graph.py     11-node discovery workflow
  app/graphs/evaluation_graph.py    13-node evaluation workflow
  app/graphs/checkpointer.py        MemorySaver | Sqlite | Postgres checkpointer
  app/discovery/{base,registry,google_places,duckduckgo,brave,location,
                 planner,aggregator,normalizer,cleaner,deduplicator}.py
  app/research/{orchestrator,http_client,parser,extractor,playwright_client,
                tavily,signals,evidence}.py
  app/evaluation/{llm,steps,prompts,scoring,services_kb}.py
  app/outreach/providers.py         OutreachProvider: Null | SMTP
  app/services/{job,discovery,research,evaluation,outreach}_service.py
  scripts/run_e2e.py                real end-to-end smoke test
  render.yaml                       Render Blueprint (API + worker + Postgres + Redis)
  Dockerfile / docker-compose.yml   container build + local full stack

FRONTEND (web/)
  src/app/api/backend/[...path]/route.ts   the proxy
  src/app/**/page.tsx                       11 route files (9 pages + 2 dynamic [id])
  src/lib/api/{client,endpoints,types}.ts   typed API layer
  src/lib/query/{keys,hooks}.ts             TanStack Query hooks + polling
  src/lib/realtime/use-job-stream.ts        SSE → cache
  src/components/{layout,dashboard,discovery,jobs,prospects,prospect,outreach,
                  shared,ui}/*
  e2e/                                      Playwright flow + mock backend
```
