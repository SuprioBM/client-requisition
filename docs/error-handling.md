# Error handling

## Taxonomy

`app/core/errors.py::ErrorCode` — a closed enum. `RETRYABLE_ERROR_CODES` /
`NON_RETRYABLE_ERROR_CODES` drive the worker's retry policy.

Groups: `CONFIG_*`, `LOCATION_*`, `PROVIDER_*`, `WEBSITE_*`, `PLAYWRIGHT_FAILED`,
`DATABASE_ERROR`, `REDIS_ERROR`, `LLM_*`, `JOB_*`, `OUTREACH_NOT_CONFIGURED`,
`DUPLICATE_OUTREACH`.

## Exceptions

`AppError` base carries `code`, `http_status`, `context`, `retryable`. Subtypes:
`ConfigError`, `ValidationError`, `NotFoundError`, `UnauthorizedError`,
`LocationError`, `ProviderError`, `WebsiteError`, `LLMError`, `DatabaseError`,
`RedisError`, `JobError`, `OutreachError`.

## API surface

Every error becomes:

```json
{ "success": false, "data": null,
  "error": { "code": "PROVIDER_TIMEOUT", "message": "…" } }
```

with the mapped HTTP status. Stack traces only in `DEBUG`. Request id echoed as
`X-Request-ID` and bound to every log line for that request.

## Worker retry policy

Retryable + attempts remaining → `retry_count++`, status back to `QUEUED`,
exponential backoff (`RETRY_BASE_DELAY_SECONDS * 2^n`, capped), re-enqueue.
Non-retryable, or attempts exhausted → status `FAILED`, `error_code` +
`error_message` stored, terminal banner printed.

Never retried: `CONFIG_MISSING/INVALID`, `PROVIDER_AUTH_FAILED`,
`PROVIDER_QUOTA_EXCEEDED`, `LLM_AUTH_FAILED`, `LOCATION_INVALID`,
`WEBSITE_SSRF_BLOCKED`, `VALIDATION_ERROR`.

## Partial success

Discovery with some providers failing → job `COMPLETED_WITH_WARNINGS`, warnings
list on the job, successful results kept. All providers failing with nothing
saved → `FAILED` / `discovery_providers_unavailable`.

Zero results (all providers OK, nothing matched) → `COMPLETED`, `results: []` —
not an error.

## Terminal banners (`app/core/banners.py`)

```
============================================================
DISCOVERY JOB FAILED
============================================================
Job ID:   9f32...
Stage:    google_discovery
Error:    PROVIDER_QUOTA_EXCEEDED
Detail:   quota exceeded
Action:
- Inspect GET /api/v1/jobs/{id} for details
- Fix the underlying cause, then POST /api/v1/jobs/{id}/retry
============================================================
```

Config errors print a `CONFIGURATION ERROR` banner naming the missing variable
and the affected feature, then exit non-zero.

## No hidden errors

No bare `except: pass`. Every caught exception is either handled intentionally,
logged, reflected in job state, or re-raised. Provider fallbacks
(Google → DDG/Brave) are logged and recorded in job/provider metadata.

## Recovery

- **Worker crash mid-job**: lease expires → sweeper (`find_stale`) requeues it.
  The atomic `acquire_lease` UPDATE prevents two workers taking the same job.
- **Redis down (dev)**: queue falls back to DB polling.
- **LLM mid-graph failure**: checkpointer (thread_id = job_id) resumes from the
  failed node on retry; research/evidence already persisted are reused.
