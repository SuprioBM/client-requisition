# Deployment

## Components

```
FastAPI (app.main:app)  +  Worker (python -m app.workers.worker)  +  Postgres  +  Redis
```

No n8n, no microservices. n8n / CRM / Slack / Gmail automations are explicitly
out of scope for V1 and would attach later via the existing API.

## Docker

`docker compose up --build` brings up:

| Service | Notes |
|---|---|
| `db` | postgres:16, healthchecked |
| `redis` | redis:7, healthchecked |
| `api` | runs `alembic upgrade head` then uvicorn on :8000 |
| `worker` | `python -m app.workers.worker` |

Both `api` and `worker` read `.env` and override `DATABASE_URL` / `REDIS_URL` to
the compose network.

## Manual

```bash
python -m venv .venv && .venv/Scripts/activate       # or source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env      # fill in keys
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000      # embedded worker in dev
python -m app.workers.worker                          # separate worker (prod)
```

## Configuration modes (`APP_ENV`)

| | development | testing | production |
|---|---|---|---|
| verbose logs / debug detail in errors | yes | — | no (sanitised) |
| embedded worker | yes (unless `RUN_EMBEDDED_WORKER=false`) | no | no |
| Redis fallback to DB polling | yes | yes | **no** — hard fail |
| `API_KEY` required | no | no | **yes** |
| accidental real sends | prevented (Null provider) | prevented | requires SMTP_* + approval |

## Health

- `GET /health` — liveness
- `GET /health/ready` — DB + Redis + capability summary; `success:false` if a
  dependency is down (use for k8s readiness).

## Migrations

Alembic. `alembic revision --autogenerate -m "..."` then review, then
`alembic upgrade head`. The compose `api` service runs `upgrade head` on start.

## Scaling

Multiple workers are safe: job claim is an atomic
`UPDATE jobs SET status='RUNNING' WHERE id=? AND status='QUEUED'`. Stale leases
are swept and requeued. For multi-worker LangGraph checkpointing set
`LANGGRAPH_CHECKPOINT_DB` to a `postgresql://` URL (needs
`langgraph-checkpoint-postgres` + `psycopg[binary]`, already in
`requirements.txt`).

---

# Deploy: Vercel (frontend) + Render (backend)

Topology:

```
   Vercel                         Render
┌──────────────┐   HTTPS/JSON  ┌─────────────────────────────────┐
│ Next.js      │ ─── + key ──► │ cra-api   (web service, Docker) │
│ dashboard    │ ◄──────────── │   uvicorn app.main:app          │
│ + /api/backend proxy         │ cra-worker (background worker)  │
│              │   SSE  ─────► │   python -m app.workers.worker  │
└──────────────┘  (direct, via │ cra-postgres (managed Postgres) │
   NEXT_PUBLIC_SSE_BASE)       │ cra-redis    (managed Redis)    │
                               └─────────────────────────────────┘
```

## A. Backend on Render (Blueprint)

The repo ships **`render.yaml`** — a Blueprint that provisions the API web
service, the background worker, Postgres, and Redis in one go.

1. Push this repo to GitHub/GitLab.
2. Render dashboard → **New +** → **Blueprint** → pick the repo. Render reads
   `render.yaml` and shows the 4 resources. Apply.
3. First deploy will pause on the `sync: false` env vars. Set them on the
   **cra-api** and **cra-worker** services:
   - `GROQ_API_KEY` (required), `GROQ_MODEL` is pre-filled `openai/gpt-oss-120b`
   - `GOOGLE_MAPS_API_KEY` (primary discovery; enable **Places API (New)** +
     **Geocoding API** + **billing** in Google Cloud)
   - `BRAVE_SEARCH_API_KEY`, `TAVILY_API_KEY` (optional)
   - `CORS_ORIGINS` → your Vercel URL(s), comma-separated, e.g.
     `https://cra-dashboard.vercel.app` (add the preview domain too if you use
     preview deploys)
   - `OUTREACH_SENDER_NAME`, and `SMTP_*` if you want real email sending
4. `API_KEY` is auto-generated (`generateValue: true`). Open **cra-api → Environment**,
   copy its value — you need it for Vercel in step B.
5. `DATABASE_URL` and `REDIS_URL` are wired automatically from the managed
   Postgres/Redis. `alembic upgrade head` runs as the **Pre-Deploy Command**
   before each release, so the schema is always current.
6. Wait for **cra-api** to go live; check `https://cra-api.onrender.com/health`
   → `{"success":true,...}`.

**Without the Blueprint** (manual services), the equivalents are:

| Service | Type | Build | Start |
|---|---|---|---|
| API | Web Service, Docker (`./Dockerfile`) | (Dockerfile) | `uvicorn app.main:app --host 0.0.0.0 --port $PORT`; Pre-Deploy: `alembic upgrade head` |
| Worker | Background Worker, Docker (`./Dockerfile`) | (Dockerfile) | `python -m app.workers.worker` |
| Postgres | Render PostgreSQL | — | — |
| Redis | Render Key Value / Redis, `maxmemory-policy noeviction` | — | — |

Set on **both** API and worker: `APP_ENV=production`, `DATABASE_URL`,
`REDIS_URL`, `API_KEY` (same value), `GROQ_API_KEY`, `GROQ_MODEL`,
`GOOGLE_MAPS_API_KEY`, `LANGGRAPH_CHECKPOINT_DB` = the Postgres connection string.
Set on the API only: `CORS_ORIGINS`, `RUN_EMBEDDED_WORKER=false`.

If you prefer a non-Docker Python service on Render:
build `pip install -r requirements.txt && python -m playwright install --with-deps chromium`
(or set `PLAYWRIGHT_ENABLED=false` to skip the ~300 MB Chromium download — website
research still works over HTTPX, only the JS-render fallback is disabled).

### Render free-tier caveats
- Web services **sleep after 15 min idle**; the next request cold-starts (~30 s).
  A sleeping API means the dashboard shows "Backend unavailable" until it wakes.
- Background workers on free tier also sleep — **use at least the Starter plan
  for the worker** if you want jobs to run reliably, or hit the API periodically.
- Free Postgres is **deleted after 90 days**. Use a paid instance or an external
  Postgres (Supabase, Neon) for anything real — just set `DATABASE_URL`.

## B. Frontend on Vercel

1. Vercel → **Add New… → Project** → import the repo.
2. **Root Directory: `web`** (important — the Next app is not at the repo root).
   Framework preset auto-detects Next.js. Build command `next build`, output
   `.next` — defaults are fine.
3. **Environment Variables** (Project Settings → Environment Variables):

   | Name | Value | Notes |
   |---|---|---|
   | `BACKEND_URL` | `https://cra-api.onrender.com` | your Render API URL — **no** `NEXT_PUBLIC_` |
   | `BACKEND_API_KEY` | *(the `API_KEY` from Render step A.4)* | server-only; injected by the proxy |
   | `NEXT_PUBLIC_SSE_BASE` | `https://cra-api.onrender.com` | **recommended** — see below |

4. Deploy. Open the Vercel URL; the dashboard status bar should show
   API/Worker/Database online.
5. Go back to Render and make sure `CORS_ORIGINS` on **cra-api** contains the
   exact Vercel URL (and any `*.vercel.app` preview URL you'll use).

### Why `NEXT_PUBLIC_SSE_BASE`

The job-monitor SSE stream can stay open for minutes. Vercel serverless
functions have a max duration (10 s Hobby, 60 s Pro), so routing SSE **through**
the Next proxy would cut the stream repeatedly. Setting `NEXT_PUBLIC_SSE_BASE`
to the Render API origin makes the browser's `EventSource` connect **directly**
to `GET /api/v1/jobs/{id}/stream` (an unauthenticated endpoint — no secret
exposed), bypassing the function entirely. The backend just needs the Vercel
origin in `CORS_ORIGINS`.

If you leave `NEXT_PUBLIC_SSE_BASE` unset, everything still works: the stream
goes through the proxy, drops at the function timeout, `EventSource`
auto-reconnects, and the 2 s polling fallback (`useJob(id,{poll:true})`) covers
the gaps — the monitor is just slightly less instant.

## C. Post-deploy smoke test

1. Open the Vercel dashboard → **Discover** → submit
   `Bangladesh / Dhaka / dental / 10 / 10` → **Start Discovery**.
2. You land on `/jobs/{id}`; the pipeline advances (validate → resolve →
   plan → google/ddg/brave → aggregate → normalize → clean → deduplicate → save)
   and the "live" indicator shows if SSE connected.
3. When it completes, **Prospects** lists the discovered businesses.
4. Open one with a website → **Evaluate** → watch the 13-stage evaluation graph →
   evidence, pain points, solutions, score appear.
5. **Outreach** → open the draft → **Approve** (confirm) → **Send** →
   `NOT_CONFIGURED` (or `SENT` if you configured SMTP).

## D. Updating

Push to the default branch. Render redeploys the API (running
`alembic upgrade head` first) and the worker; Vercel redeploys the frontend.
New migrations: `alembic revision --autogenerate -m "..."`, review, commit —
they apply automatically on the next Render deploy.

## Known limitations

- DuckDuckGo (`ddgs`) frequently returns 0 results (upstream Bing HTML
  scraping); Google Places is the reliable primary. Brave fills the gap when
  `BRAVE_SEARCH_API_KEY` is set.
- Google Geocoding needs billing enabled; without it, location falls back to a
  small offline gazetteer (major cities only).
- Groq free tier is 8k tokens/minute — a full evaluation (7 LLM calls) is paced
  by the client's 429 backoff and can take a few minutes. A paid tier removes
  this.
- WhatsApp sending is not integrated (drafts + approval only).
- Playwright requires `playwright install chromium` (Docker image does this).
