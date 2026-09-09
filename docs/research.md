# Research & Evidence

Turns a prospect into **objective, sourced signals** and a list of `Evidence`
rows. No interpretation happens here — that is the LLM's job in evaluation.

## Pipeline (`app/research/orchestrator.py`)

```
website known?
  yes -> HTTPX fetch (SSRF-guarded, size-capped, timeout)
           usable HTML? -> BeautifulSoup structure + Trafilatura clean text
                           (+ up to 2 key internal pages: contact/book/services)
           thin / JS?   -> Playwright render -> re-parse
  no / failed / thin -> DuckDuckGo + Brave to find the official site / socials
                        still thin -> Tavily (only if TAVILY_API_KEY set)
-> deterministic signals -> Evidence[]
```

Cost control: ≤3 HTTP page fetches, Playwright only when
`looks_js_rendered()` is true, Tavily only as a last resort, raw HTML never sent
to the LLM.

## Fetch (`http_client.py`)

- `validate_public_url` on the initial URL **and every redirect hop** — blocks
  `localhost`, private/link-local/reserved IPs, cloud metadata (169.254.169.254).
- Hard timeout, `RESEARCH_MAX_RESPONSE_BYTES` cap, content-type allow-list
  (HTML/plain only; PDFs and binaries rejected).
- Returns a `FetchResult` with a classified `WebsiteStatus`
  (`ACTIVE|REDIRECTED|NOT_FOUND|TIMEOUT|FORBIDDEN|SERVER_ERROR|INVALID|UNKNOWN`),
  never raises for ordinary HTTP failures.

## Signals (`signals.py`)

Objective facts only, e.g. `has_booking_mechanism`, `has_primary_cta`,
`is_https`, `has_viewport_meta`, `service_pages_found`, `social_profiles`,
`technology_signals`, `total_text_length`, plus business signals (rating, review
count, public contact channels).

## Evidence (`evidence.py`)

Each `Evidence` row: `observation` (hedged wording — "No online appointment
mechanism **was identified on the researched pages**"), `source_type`,
`source_url`, `confidence` (0–1, calibrated per signal type), `data_origin`
(`VERIFIED` for direct observation, `INFERRED` for fingerprints/search snippets).
Rows get DB ids; the LLM cites those ids.

## Caching (`research_service.py`)

`ResearchRepository.fresh_run` returns a prior run if it completed within
`RESEARCH_CACHE_TTL_SECONDS` (default 7 days). `force=true` bypasses it.
A `content_hash` of the extracted text is stored for staleness checks.

## Runs

Every research attempt is a `research_runs` row (`schema_version`, `status`
`COMPLETED|PARTIAL|FAILED`, `sources_used`, `website_status`, `signals` JSON)
with its `evidence` children — full history is retained.
