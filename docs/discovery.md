# Discovery

Finds candidate businesses. Answers "who is out there?" — nothing more.

## Flow (LangGraph `discovery_graph`)

```
validate_search -> resolve_location -> plan_queries
 -> google_discovery -> duckduckgo_discovery -> brave_discovery
 -> aggregate -> normalize -> clean -> deduplicate -> save
```

Each provider node is independent: a provider failure appends a `failed`
`ProviderRun` to state and the graph continues. `aggregate` records whether any
attempted provider succeeded; if none did and nothing was saved, the job fails
with `PROVIDER_UNAVAILABLE` / `discovery_providers_unavailable`.

## Providers (`app/discovery/`)

| Provider | Role | Key | Failure mapping |
|---|---|---|---|
| `GooglePlacesProvider` | PRIMARY | `GOOGLE_MAPS_API_KEY` | quota→`PROVIDER_QUOTA_EXCEEDED`, billing/403→`PROVIDER_AUTH_FAILED`, 429→`PROVIDER_RATE_LIMITED`, timeout→`PROVIDER_TIMEOUT` |
| `DuckDuckGoProvider` | SECONDARY (website discovery) | none | rate/timeout classified from message |
| `BraveProvider` | SECONDARY | `BRAVE_SEARCH_API_KEY` | standard HTTP mapping; skipped cleanly if no key |

All implement `BusinessDiscoveryProvider`; business logic depends only on the
interface. Swap providers via `registry.set_provider_factory` (used by tests).

- **Google** gets the plain industry queries and handles location itself
  (`locationBias` circle from the resolved lat/lng).
- **DuckDuckGo / Brave** get location-baked web-search queries; directory hosts
  (facebook, yelp, justdial, …) are filtered out.

## Location resolution (`location.py`)

Google Geocoding API → offline gazetteer → **hard 400**. Never a silent
assumption. `ZERO_RESULTS`→`LOCATION_INVALID`, multiple localities→
`LOCATION_AMBIGUOUS` (candidates returned), `REQUEST_DENIED`/`OVER_QUERY_LIMIT`→
fall through to gazetteer.

## Query planner (`planner.py`)

Deterministic (no LLM). Curated industry synonym map + light generic expansion,
capped at `MAX_QUERIES_PER_PLAN`. Avoids redundant near-duplicate queries.

## Normalize / clean / dedupe

- **normalize** (`normalizer.py`): canonical domain (offline `tldextract`),
  phone→E.164 (`phonenumbers`), canonical business name (legal-suffix stripped),
  address whitespace/punctuation.
- **clean** (`cleaner.py`): drop empty/malformed/non-business ("Top 10 …",
  "Home", listicles) and candidates with no locating signal at all. Uncertain
  web-only hits are **flagged `REVIEW`, never deleted**.
- **deduplicate** (`deduplicator.py`): union-find over strong signals
  (`google_place_id`, canonical domain, E.164 phone) then bounded fuzzy
  name+address. **Branch protection**: candidates with clearly different
  addresses, different place ids, or different `- <area>` name qualifiers are
  never merged.

## Persistence

`ProspectRepository.upsert_from_cluster` is idempotent: matches an existing
prospect by place id / domain / phone before inserting, fills only missing
fields (never overwrites), and de-dupes `prospect_sources` on
`(provider, source_identity)`. Re-running the same discovery creates 0 new rows.
