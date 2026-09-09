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
`LANGGRAPH_CHECKPOINT_DB` to a `postgresql://` URL.

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
