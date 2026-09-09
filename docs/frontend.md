# Frontend — Operations Dashboard

Lives in `web/`. Next.js 15 App Router + TypeScript + Tailwind + TanStack Query.
Full detail in `web/README.md`; this file covers how it fits the system.

## Responsibility boundary

```
Next.js dashboard        FastAPI backend            Worker / LangGraph
  input                    business logic             long-running workflows
  display                  discovery / research
  monitor (SSE + poll)     LLM / scoring / dedup
  filter / edit            database / jobs
  human approval           provider integrations
```

The dashboard contains **no business logic**. It never calls Google, an LLM, or a
database directly — only the backend HTTP API.

## Proxy + secrets

The browser talks only to a same-origin Next route,
`web/src/app/api/backend/[...path]/route.ts`, which forwards to `BACKEND_URL` and
adds `X-API-Key: $BACKEND_API_KEY` server-side. Consequences:

- No API key or backend origin in client JS (satisfies "never expose secrets").
- No browser CORS to configure (same origin). The backend still sets
  `CORS_ORIGINS` for direct/other clients.
- SSE passes through because the proxy streams `upstream.body` unchanged.

## Real-time strategy

Backend offers **SSE** (`GET /api/v1/jobs/{id}/stream`) — chosen over WebSocket
(simpler, one-way, survives the proxy). Fallback is polling.

- **Job monitor** (`/jobs/[id]`): `useJobStream(id)` opens the SSE stream, writes
  each job payload into the `job(id)` query cache, and on every stage change
  invalidates `prospects`, `dashboard-stats`, `activity`, and the subject
  prospect's `profile`/`research`/`evaluation`/`outreach`. On terminal status it
  invalidates the job lists too. `useJob(id,{poll:true})` runs alongside as a
  belt-and-braces 2 s poll while non-terminal.
- **Elsewhere**: TanStack Query `refetchInterval`, adaptive — e.g. the jobs list
  polls every 3 s while any job is active, 15 s otherwise; dashboard stats 10 s;
  prospect detail does not auto-poll (it is invalidated by the job stream).

Backend support for live pipeline progress: the discovery/evaluation job handlers
`graph.astream(...)` the LangGraph run and persist `current_stage` +
`progress.provider_runs` + counters onto the `jobs` row after each node, so the
SSE payload carries real per-stage state.

## Backend endpoints added for the dashboard

`GET /api/v1/jobs` (list/filter), `POST /api/v1/jobs/{id}/retry`,
`GET /api/v1/jobs/{id}/stream` (SSE);
`GET /api/v1/dashboard/{health,stats,activity,settings}` and
`/dashboard/analytics/{providers,research}`;
`GET /api/v1/outreach` (list all), `PATCH /api/v1/outreach/{id}` (save edit
without approving);
`POST /api/v1/prospects/bulk/{research,evaluate}`,
`GET /api/v1/prospects/{id}/evaluations` (run history);
prospect list enriched with latest evaluation score + `min_score`/`q`/`sort=score`.

## Uncertainty preservation

The UI never flattens backend uncertainty into green "success":

- Pain-point confidence shown verbatim: `CONFIRMED | LIKELY | POSSIBLE |
  NOT_ENOUGH_EVIDENCE`.
- Website analysis is tri-state: `✓ Found` / `— Not detected` / `? Unknown` —
  "not detected" is explicitly labelled as "no such element on the researched
  pages, not a confirmed absence".
- Evidence confidence rendered as `high/medium/low` + the raw 0–1 value.
- Score shows all five component dimensions + a per-dimension reason tooltip,
  never just the total.
- Missing fields render "Not available", not blank.

## Tests

- `npm run test` — vitest: API client (envelope unwrap, error mapping, malformed
  body, network error), pipeline stage-state logic, badge components incl.
  undefined-tolerance.
- `npm run e2e` — Playwright: full operator flow against a mocked backend
  (discover → job monitor → prospect intelligence → outreach approve-with-confirm
  → send → NOT_CONFIGURED), plus a backend-down → retry-able-error case.
