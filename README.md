# Client Requisition Agent

AI-powered agent that **discovers** potential business clients, **researches** them,
identifies **evidence-backed** pain points, maps them to services you can provide,
**scores** the opportunity, and drafts **personalized outreach** for human approval.

Core principle — the AI never invents a business problem just because a service
can be sold. Every non-trivial claim references stored evidence with provenance:

```
SOURCE → EVIDENCE → OBSERVATION → PAIN POINT → SOLUTION → VALUE → OUTREACH
```

Three separate phases: **Discovery** (who is out there?) · **Evaluation** (is
there a real opportunity?) · **Outreach** (start the conversation).

---

## Status: V1 complete — backend + operations dashboard

All phases implemented, wired end to end, and exercised against the real Google
Places + Groq APIs through the Next.js dashboard.

- **Backend**: 92 tests pass with **zero paid services** (SQLite + `fakeredis` +
  `respx` + a fake LLM). `ruff` and `mypy` clean.
- **Frontend** (`web/`): 14 vitest unit tests + 2 Playwright e2e flows pass;
  `tsc` + `eslint` clean; `next build` succeeds.

| Area | State |
|---|---|
| Config + validation banner, structured logging, error taxonomy | ✅ |
| DB models (13 tables) + Alembic migrations | ✅ |
| Discovery: Google Places / DuckDuckGo / Brave behind an interface | ✅ |
| Location resolution (geocode → gazetteer → 400) | ✅ |
| Normalize · clean · deduplicate (with branch protection) · idempotent persist | ✅ |
| Redis-list queue (+ DB-poll fallback), worker, job state machine, leases, stale recovery | ✅ |
| LangGraph discovery graph + evaluation graph + checkpointing | ✅ |
| Website research: HTTPX → BS4/Trafilatura → Playwright fallback → Tavily fallback | ✅ |
| SSRF guard (initial URL + every redirect hop) | ✅ |
| Evidence model (sourced, confidence-scored, cited by AI) | ✅ |
| LLM evaluation: pain points → solutions → opportunity → deterministic scoring | ✅ |
| Structured LLM output (Pydantic-validated, constrained retry, rate-limit backoff) | ✅ |
| Outreach strategy + email + WhatsApp drafts | ✅ |
| Human approval workflow, duplicate protection, follow-up tracking | ✅ |
| Sending behind an interface (Null / SMTP) — never a fake `SENT` | ✅ |
| Next.js operations dashboard (`web/`) — real-time SSE, no manual refresh | ✅ |
| Tests (unit / integration / failure / frontend / e2e), Docker, docs | ✅ |

See `docs/` for detail on each phase and `web/README.md` for the dashboard.

---

## Technology

- **API**: FastAPI + Pydantic v2
- **DB**: PostgreSQL / Supabase via SQLAlchemy 2 async (`asyncpg`); SQLite for tests
- **Cache / queue**: Redis list queue (no Celery/RQ — portable to Windows). DB-poll
  fallback outside production if Redis is down.
- **Orchestration**: LangGraph (workflow/state) + LangChain (model glue)
- **LLM**: Groq (`GROQ_MODEL`, default `openai/gpt-oss-120b`)
- **Discovery**: Google Places (primary) · DuckDuckGo + Brave (secondary)
- **Research**: HTTPX → BeautifulSoup + Trafilatura → Playwright (fallback) → Tavily (selective)

No n8n in V1 (explicitly out of scope).

---

## Quick start — local, zero infra

```bash
python -m venv .venv
.venv\Scripts\activate                 # Windows
# source .venv/bin/activate             # macOS / Linux

pip install -r requirements-dev.txt
playwright install chromium

cp .env.example .env
# minimal local .env:
#   APP_ENV=development
#   DATABASE_URL=sqlite+aiosqlite:///./requisition.db
#   REDIS_URL=redis://localhost:6379/0     (unreachable is fine in dev)
#   GROQ_API_KEY=...   GOOGLE_MAPS_API_KEY=...   (for real runs)

alembic upgrade head
uvicorn app.main:app --reload
```

- Operator UI: http://localhost:8000/
- API docs: http://localhost:8000/docs
- Health: `/health` · Readiness: `/health/ready`

In `development` the worker runs **embedded** in the API process, so a single
`uvicorn` command runs the whole pipeline. Set `RUN_EMBEDDED_WORKER=false` to run
it separately.

## Quick start — Docker

```bash
cp .env.example .env      # fill in keys
docker compose up --build
```

Postgres + Redis + API (migrates first) + worker.

## Worker (production / separate process)

```bash
python -m app.workers.worker
```

## Operations dashboard (`web/`)

```bash
cd web
npm install
cp .env.example .env.local        # BACKEND_URL + optional BACKEND_API_KEY (server-only)
npm run dev                        # http://localhost:3000
```

The browser only ever talks to a same-origin Next proxy (`/api/backend/*`), which
injects the backend URL and API key server-side — no secret or CORS config
reaches the client, and SSE is streamed through unchanged. See `web/README.md`.

## Tests / checks

```bash
# backend
pytest -q            # 92 tests, no paid services
ruff check app
mypy app

# frontend (in web/)
npm run test         # vitest unit tests
npm run e2e          # Playwright e2e (mocked backend)
npm run typecheck
npm run build
```

## Real end-to-end smoke test (uses your real API keys, costs a few calls)

```bash
python scripts/run_e2e.py --industry dentist --city Dhaka --country Bangladesh
```

---

## API

```
POST /api/v1/discovery/search              -> { job_id, status }
POST /api/v1/discovery/plan-preview        -> generated query plan
GET  /api/v1/discovery/jobs/{job_id}
GET  /api/v1/jobs/{job_id}                  -> status, current_stage, result, error_code
POST /api/v1/jobs/{job_id}/cancel

GET  /api/v1/prospects                      -> filter: industry,city,status,website_exists; sort; paginate
GET  /api/v1/prospects/{id}
POST /api/v1/prospects/{id}/research        -> job
GET  /api/v1/prospects/{id}/research        -> run + evidence
POST /api/v1/prospects/{id}/evaluate        -> job
GET  /api/v1/prospects/{id}/evaluation      -> opportunity, per-dimension score, pain points, solutions
GET  /api/v1/prospects/{id}/profile         -> full client intelligence profile
POST /api/v1/prospects/{id}/outreach/generate
GET  /api/v1/prospects/{id}/outreach

GET  /api/v1/outreach/{id}
POST /api/v1/outreach/{id}/approve          -> { edited_body? }
POST /api/v1/outreach/{id}/reject
POST /api/v1/outreach/{id}/send             -> APPROVED only; NOT_CONFIGURED if no provider
```

Responses: `{ "success": true, "data": {...}, "error": null }` or
`{ "success": false, "data": null, "error": { "code": "...", "message": "..." } }`.
Mutating / outreach endpoints require `X-API-Key` when `API_KEY` is set
(always in production).

---

## Environment variables

See `.env.example`. `DATABASE_URL` and `REDIS_URL` are mandatory (`API_KEY` too in
production) — missing one prints a `CONFIGURATION ERROR` banner and exits.
`GOOGLE_MAPS_API_KEY`, `BRAVE_SEARCH_API_KEY`, `TAVILY_API_KEY`, `GROQ_API_KEY`
are feature-specific: absent → that capability is disabled and logged, the app
still runs.

---

## Known limitations

- **DuckDuckGo** (`ddgs`) often returns 0 results (upstream HTML scraping is
  flaky). Google Places is the reliable primary; set `BRAVE_SEARCH_API_KEY` for a
  second web source.
- **Google Geocoding** needs billing enabled on the GCP project; without it,
  location falls back to a small offline gazetteer (major cities).
- **Groq free tier** = 8k tokens/min. A full evaluation is 7 LLM calls; the
  client paces itself with 429 backoff, so it can take a few minutes. A paid
  tier removes this.
- **WhatsApp sending** is not integrated (draft + approval only). Email sends via
  SMTP when `SMTP_*` is configured, otherwise reports `NOT_CONFIGURED`.
- **Playwright** needs `playwright install chromium` (the Docker image does it).

## Remaining optional improvements

- Staged research filtering config surface (criteria are in code, not yet an API knob)
- n8n / CRM / Slack / Gmail automation hooks (deliberately out of V1 scope)
- Richer frontend (current UI is intentionally minimal, backend-first)
- Provider performance analytics view over the stored `provider` run metadata
