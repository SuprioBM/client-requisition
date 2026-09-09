import type { Page, Route } from "@playwright/test";

/** In-memory fake of the FastAPI backend, wired at the Next proxy boundary. */
export function makeState() {
  return {
    jobStatus: "RUNNING" as string,
    jobStage: "google_places_discovery" as string,
    prospectStatus: "EVALUATED",
    outreachStatus: "PENDING_APPROVAL",
  };
}

const ok = (data: unknown) => ({
  status: 200,
  contentType: "application/json",
  body: JSON.stringify({ success: true, data, error: null }),
});

export async function installMockBackend(page: Page, state = makeState()) {
  await page.route("**/api/backend/**", (route: Route) => {
    const url = new URL(route.request().url());
    const p = url.pathname.replace("/api/backend", "");
    const method = route.request().method();

    if (p === "/api/v1/dashboard/health")
      return route.fulfill(
        ok({
          components: { api: "online", worker: "online", redis: "online", database: "online" },
          env: "testing",
          capabilities: { google_places_discovery: true, llm_evaluation_and_outreach: true },
        }),
      );

    if (p === "/api/v1/dashboard/stats")
      return route.fulfill(
        ok({
          prospects: { total: 1, by_status: {}, new: 0, researching: 1, evaluating: 0, evaluated: 1, outreach_ready: 1, contacted: 0 },
          opportunities: { high: 1, evaluations_total: 1 },
          outreach: { by_status: {}, awaiting_approval: 1, approved: 0, sent: 0 },
          jobs: { by_status: {}, active: state.jobStatus === "RUNNING" ? 1 : 0, failed: 0 },
        }),
      );

    if (p === "/api/v1/dashboard/activity") return route.fulfill(ok([]));
    if (p === "/api/v1/dashboard/analytics/providers") return route.fulfill(ok([]));

    if (p === "/api/v1/discovery/plan-preview")
      return route.fulfill(ok({ queries: ["dental clinic", "dentist"], location_label: "Dhaka" }));

    if (p === "/api/v1/discovery/search" && method === "POST") {
      return route.fulfill(ok({ job_id: "job-1", status: "QUEUED" }));
    }

    if (p === "/api/v1/jobs" || p === "/api/v1/jobs/")
      return route.fulfill(ok({ items: [job(state)], total: 1, limit: 50, offset: 0 }));

    if (p === "/api/v1/jobs/job-1/stream") {
      // finish immediately for the test
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: `event: job\ndata: ${JSON.stringify({ ...job(state), status: "COMPLETED", current_stage: "save" })}\n\nevent: done\ndata: {}\n\n`,
      });
    }

    if (p === "/api/v1/jobs/job-1")
      return route.fulfill(ok({ ...job(state), status: "COMPLETED", current_stage: "COMPLETED" }));

    if (p === "/api/v1/prospects" || p === "/api/v1/prospects/")
      return route.fulfill(ok({ items: [prospect()], total: 1, limit: 50, offset: 0 }));

    if (p === "/api/v1/prospects/p1/profile") return route.fulfill(ok(profile(state)));
    if (p === "/api/v1/prospects/p1") return route.fulfill(ok({ ...prospect(), sources: [], contacts: [], provider_metadata: {} }));
    if (p === "/api/v1/prospects/p1/research") return route.fulfill(ok(research()));
    if (p === "/api/v1/prospects/p1/evaluation") return route.fulfill(ok(evaluation()));
    if (p === "/api/v1/prospects/p1/evaluations") return route.fulfill(ok([evaluation()]));
    if (p === "/api/v1/prospects/p1/outreach") return route.fulfill(ok([outreachMsg(state)]));

    if (p === "/api/v1/prospects/p1/evaluate" && method === "POST")
      return route.fulfill(ok({ job_id: "job-1", status: "QUEUED" }));
    if (p === "/api/v1/prospects/p1/research" && method === "POST")
      return route.fulfill(ok({ job_id: "job-1", status: "QUEUED" }));

    if (p === "/api/v1/outreach" || p === "/api/v1/outreach/")
      return route.fulfill(ok({ items: [outreachMsg(state)], total: 1, limit: 100, offset: 0 }));
    if (p === "/api/v1/outreach/m1") return route.fulfill(ok(outreachMsg(state)));
    if (p === "/api/v1/outreach/m1/approve" && method === "POST") {
      state.outreachStatus = "APPROVED";
      return route.fulfill(ok({ id: "m1", status: "APPROVED" }));
    }
    if (p === "/api/v1/outreach/m1/send" && method === "POST") {
      state.outreachStatus = "NOT_CONFIGURED";
      return route.fulfill(ok({ id: "m1", status: "NOT_CONFIGURED", detail: "no provider" }));
    }
    if (p === "/api/v1/dashboard/settings")
      return route.fulfill(ok({ app_env: "testing", groq_model: "x", max_queries_per_plan: 6, discovery_provider_concurrency: 3, research_concurrency: 4, research_http_timeout_seconds: 15, research_cache_ttl_seconds: 604800, playwright_enabled: false, worker_job_lease_seconds: 900, embedded_worker: false, capabilities: {} }));

    return route.fulfill(ok(null));
  });
}

const job = (s: ReturnType<typeof makeState>) => ({
  id: "job-1",
  job_type: "DISCOVERY",
  status: s.jobStatus,
  params: { city: "Dhaka", industry: "dental" },
  current_stage: s.jobStage,
  progress: { stage: s.jobStage, percent: 60 },
  result: { prospects_created: 1, unique_clusters: 1, raw_candidates: 3, any_provider_succeeded: true },
  warnings: [],
  error_code: null,
  error_message: null,
  retry_count: 0,
  prospect_id: null,
  started_at: "2026-09-09T00:00:00Z",
  completed_at: null,
  created_at: "2026-09-09T00:00:00Z",
  updated_at: "2026-09-09T00:00:00Z",
});

const prospect = () => ({
  id: "p1",
  business_name: "ABC Dental",
  normalized_name: "abc dental",
  industry: "dental",
  country: "Bangladesh",
  city: "Dhaka",
  address: "12 Road",
  latitude: null,
  longitude: null,
  phone: "+8801712345678",
  phone_e164: "+8801712345678",
  email: null,
  website: "https://abcdental.example",
  canonical_domain: "abcdental.example",
  google_place_id: "P1",
  rating: 4.6,
  review_count: 88,
  status: "OUTREACH_DRAFTED",
  quality_status: "OK",
  record_kind: "REAL",
  last_researched_at: "2026-09-09T00:00:00Z",
  last_evaluated_at: "2026-09-09T00:00:00Z",
  created_at: "2026-09-09T00:00:00Z",
  updated_at: "2026-09-09T00:00:00Z",
  evaluation: { score_total: 82, is_opportunity: true, commercial_potential: "MEDIUM" },
});

const research = () => ({
  research_run_id: "r1",
  status: "COMPLETED",
  schema_version: "v1",
  website_status: "ACTIVE",
  website_final_url: "https://abcdental.example",
  sources_used: ["direct_http"],
  signals: { website: { is_https: true, has_booking_mechanism: false }, business: {} },
  social_profiles: {},
  completed_at: "2026-09-09T00:00:00Z",
  evidence: [
    {
      id: "e1",
      type: "WEBSITE_CONTENT",
      source: "direct_http",
      source_url: "https://abcdental.example",
      observation: "No online booking mechanism was identified on the researched pages.",
      confidence: 0.6,
      data_origin: "VERIFIED",
      collected_at: "2026-09-09T00:00:00Z",
    },
  ],
});

const evaluation = () => ({
  evaluation_run_id: "ev1",
  prompt_version: "v1",
  scoring_version: "v1",
  model: "test",
  status: "COMPLETED",
  is_opportunity: true,
  opportunity_summary: "Booking friction opportunity.",
  opportunity_reasoning: "Evidence e1 shows no booking flow.",
  commercial_potential: "MEDIUM",
  score: {
    problem_severity: 18,
    business_value: 20,
    evidence_confidence: 14,
    solution_fit: 18,
    contactability: 8,
    total: 78,
    max_total: 100,
    reasons: { problem_severity: "one medium-confidence pain point" },
  },
  pain_points: [
    {
      id: "pp1",
      category: "WEBSITE",
      title: "No online booking flow",
      description: "Customers appear to book by phone.",
      confidence: "LIKELY",
      evidence_ids: ["e1"],
    },
  ],
  solutions: [
    {
      service_category: "WEB DEVELOPMENT",
      service_name: "Booking Systems",
      why_it_fits: "Adds an online appointment flow.",
      expected_value: "Fewer missed calls.",
      confidence: "LIKELY",
      fit_rank: 1,
      pain_point_id: "pp1",
    },
  ],
  completed_at: "2026-09-09T00:00:00Z",
});

const outreachMsg = (s: ReturnType<typeof makeState>) => ({
  id: "m1",
  prospect_id: "p1",
  business_name: "ABC Dental",
  channel: "EMAIL",
  status: s.outreachStatus,
  subject: "A quick note about online booking",
  body: "Hi ABC Dental, I noticed there is no online booking on your site...",
  to_address: "hello@abcdental.example",
  strategy: {
    primary_observation: "No online booking flow.",
    primary_problem: "Booking friction.",
    primary_solution: "Online booking system.",
    value_proposition: "Reduce phone load.",
    tone: "professional",
    call_to_action: "Offer a demo call.",
    evidence_ids: ["e1"],
  },
  evidence_ids: ["e1"],
  follow_up_count: 0,
  next_follow_up_at: null,
  sent_at: null,
  events: [{ type: "drafted", detail: {}, at: "2026-09-09T00:00:00Z" }],
  created_at: "2026-09-09T00:00:00Z",
});

const profile = (s: ReturnType<typeof makeState>) => ({
  business: {
    id: "p1",
    name: "ABC Dental",
    industry: "dental",
    location: { city: "Dhaka", country: "Bangladesh", address: "12 Road" },
    website: "https://abcdental.example",
    contact: { phone: "+8801712345678", email: null },
    rating: 4.6,
    review_count: 88,
    status: "OUTREACH_DRAFTED",
    quality_status: "OK",
  },
  discovery: { sources: [{ provider: "google_places", query: "dentist", url: null }] },
  research: {
    website_status: "ACTIVE",
    signals: research().signals,
    social_profiles: {},
    evidence: research().evidence,
  },
  evaluation: evaluation(),
  outreach: [{ id: "m1", channel: "EMAIL", status: s.outreachStatus, subject: "x", created_at: "2026-09-09T00:00:00Z" }],
});
