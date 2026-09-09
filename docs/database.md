# Database

PostgreSQL / Supabase in production (SQLAlchemy 2 async + `asyncpg`).
SQLite (`aiosqlite`) for local dev and tests — models are written to be portable
(generic `JSON`, string PKs, no PG-only types). Migrations via **Alembic**
(`alembic upgrade head`); `Base.metadata.create_all` is used only by the test
suite.

## Tables

| Table | Purpose |
|---|---|
| `jobs` | async work + state machine + lease (owner, expiry, heartbeat), retry_count, current_stage, result, warnings, error_code |
| `prospects` | system of record. business fields as columns; `provider_metadata` JSON for provider extras. Unique on `canonical_domain`, `google_place_id`. `status`, `quality_status` (`OK|REVIEW|REJECTED`), `record_kind` (`REAL|MOCK|TEST`) |
| `prospect_sources` | provenance — one row per (provider, source_identity). `source_url`, `search_query`, `raw_payload` |
| `prospect_contacts` | phone/email/whatsapp with `data_origin` (`RAW|NORMALIZED|VERIFIED|INFERRED`) |
| `research_runs` | one per research attempt. `schema_version`, `status`, `sources_used`, `website_status`, `signals` JSON, `content_hash` |
| `evidence` | objective observations w/ `source_type`, `source_url`, `confidence`, `data_origin`. Referenced by AI output via id |
| `evaluation_runs` | one per evaluation. `prompt_version`, `scoring_version`, `model`, opportunity fields, 5 sub-scores + `score_total` + `score_breakdown` JSON, `llm_meta` |
| `pain_points` | `category`, `title`, `description`, `confidence`, `evidence_ids` JSON |
| `solutions` | `service_category`, `service_name`, `why_it_fits`, `expected_value`, `confidence`, `fit_rank`, `pain_point_id` |
| `outreach_messages` | `channel`, `status`, `strategy` JSON, `subject`, `body`, `edited_body`, approval fields, send fields, follow-up fields |
| `outreach_events` | append-only lifecycle events per message |
| `audit_events` | append-only audit trail (`entity_type`, `entity_id`, `action`, `actor`, `detail`) |

## Idempotency

- `prospects`: matched by place id / domain / phone before insert; missing
  fields filled, existing never overwritten.
- `prospect_sources`: `UniqueConstraint(prospect_id, provider, source_identity)`.
- Job retries reuse the same `jobs` row (`retry_count++`), never duplicate.
- Research/evaluation re-runs create new run rows (history preserved), not
  duplicates.

## Data quality separation

Provider facts (`evidence`, `prospects.rating`) and AI interpretation
(`pain_points`, `evaluation_runs`) live in different tables. `data_origin`
distinguishes `VERIFIED` observation from `INFERRED`.
