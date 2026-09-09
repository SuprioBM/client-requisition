# Client Requisition Agent — Operations Dashboard

Real-time lead-intelligence dashboard for the FastAPI backend in `../`. Lets an
operator create discovery jobs, watch the discovery → research → evaluation →
outreach pipeline run live, inspect every prospect's evidence and scoring, and
review / edit / approve generated outreach.

## Stack

- Next.js 15 (App Router) · React 19 · TypeScript
- Tailwind CSS + hand-rolled shadcn/ui primitives + Radix
- TanStack Query (server state) + TanStack Table (data grid)
- sonner (toasts) · next-themes (dark default)
- vitest + Testing Library (unit) · Playwright (e2e)

## Architecture

```
browser ──(same-origin)──► Next proxy /api/backend/[...path] ──► FastAPI (BACKEND_URL)
                                       + X-API-Key (BACKEND_API_KEY, server-only)
```

The browser never sees the backend origin or API key. The proxy
(`src/app/api/backend/[...path]/route.ts`) forwards method/body/query and streams
the response body unchanged, so Server-Sent Events (`/jobs/{id}/stream`) work
through it.

- **API layer**: `src/lib/api/{client,endpoints,types}.ts` — one typed function
  per endpoint, no scattered `fetch()`.
- **Server state**: `src/lib/query/{keys,hooks}.ts` — every query keyed and
  invalidated deliberately; adaptive polling (fast while jobs are active, slow
  when idle).
- **Real-time**: `src/lib/realtime/use-job-stream.ts` — subscribes to the job SSE
  stream and pushes updates into the query cache, invalidating dependent views so
  tables update with no manual refresh. `useJob(id,{poll:true})` is the fallback.
- **States**: `src/components/shared/states.tsx` `QueryBoundary` renders
  loading / error / empty / content for every fetch; `ErrorPanel` + retry;
  `app/error.tsx` is a per-section error boundary.

## Pages

| Route | Purpose |
|---|---|
| `/` | Dashboard: system status, KPI cards, active jobs, live prospect stream, activity feed |
| `/discover` | Discovery form + query-plan preview |
| `/jobs` · `/jobs/[id]` | Job list · live job monitor (pipeline stages, provider status, error panel + retry, result) |
| `/prospects` · `/prospects/[id]` | Data grid (sort/filter/search/columns/bulk research+evaluate/pagination) · full intelligence page |
| `/research` · `/evaluation` | Provider/research analytics · evaluated prospects by score |
| `/outreach` · `/outreach/[id]` | Tabbed by status · review with email/WhatsApp editors, channel previews, explicit approve/reject confirmation, send |
| `/settings` | Read-only backend runtime config (no secrets) |

## Setup

```bash
npm install
cp .env.example .env.local        # BACKEND_URL, optional BACKEND_API_KEY
npm run dev                        # http://localhost:3000
```

`.env.local` (server-only — no `NEXT_PUBLIC_` prefix):

```
BACKEND_URL=http://localhost:8000
BACKEND_API_KEY=                   # set to match the backend's API_KEY in production
```

## Commands

```bash
npm run dev          # dev server
npm run build        # production build
npm run test         # vitest unit tests
npm run e2e          # Playwright e2e (spins its own dev server on :3100, mocks the backend)
npm run typecheck    # tsc --noEmit
npm run lint         # next lint
```

## Notes

- AI-generated text is rendered as **plain text only** (no `dangerouslySetInnerHTML`).
- External links are validated to `http(s)` before opening.
- Nothing is sent without an explicit operator action; approval shows a
  confirmation dialog and only `APPROVED` messages can be sent.
- No business logic lives here — discovery, research, LLM, scoring, dedup all
  stay in the backend.
