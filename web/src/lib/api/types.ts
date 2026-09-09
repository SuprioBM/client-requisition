/**
 * API types — hand-maintained to match the FastAPI backend response shapes.
 * Every list endpoint returns { items, total, limit, offset }.
 * Every response is wrapped: { success, data, error }.
 */

export type ApiEnvelope<T> = {
  success: boolean;
  data: T | null;
  error: { code: string; message: string; context?: Record<string, unknown> } | null;
};

export type Page<T> = { items: T[]; total: number; limit: number; offset: number };

export type JobStatus =
  | "QUEUED"
  | "RUNNING"
  | "COMPLETED"
  | "COMPLETED_WITH_WARNINGS"
  | "FAILED"
  | "CANCELLED";

export type JobType = "DISCOVERY" | "RESEARCH" | "EVALUATION" | "OUTREACH_GENERATION";

export interface Job {
  id: string;
  job_type: JobType;
  status: JobStatus;
  params: Record<string, unknown>;
  current_stage: string | null;
  progress: {
    stage?: string;
    percent?: number;
    provider_runs?: ProviderRun[];
    counters?: Record<string, number | null>;
  };
  result: Record<string, unknown>;
  warnings: unknown[];
  error_code: string | null;
  error_message: string | null;
  retry_count: number;
  prospect_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export type ProviderRun = {
  provider: string;
  query: string;
  status: "ok" | "partial" | "failed" | "skipped";
  error_code: string | null;
  result_count: number;
  duration_ms: number;
  pages_received: number;
  started_at: string;
};

export type DiscoveryResult = {
  resolved_location?: Record<string, unknown>;
  query_plan?: { place_queries?: string[]; web_queries?: string[] };
  provider_runs?: ProviderRun[];
  raw_candidates?: number;
  after_cleaning?: number;
  flagged_for_review?: number;
  dropped?: number;
  unique_clusters?: number;
  prospects_created?: number;
  prospects_updated?: number;
  prospect_ids?: string[];
  any_provider_succeeded?: boolean;
  warnings?: string[];
  attempted?: number;
};

export type ProspectStatus =
  | "DISCOVERED"
  | "RESEARCHING"
  | "RESEARCHED"
  | "EVALUATING"
  | "EVALUATED"
  | "OUTREACH_DRAFTED"
  | "OUTREACH_APPROVED"
  | "CONTACTED"
  | "REJECTED"
  | "ARCHIVED";

export interface Prospect {
  id: string;
  business_name: string;
  normalized_name: string;
  industry: string | null;
  country: string | null;
  city: string | null;
  address: string | null;
  latitude: number | null;
  longitude: number | null;
  phone: string | null;
  phone_e164: string | null;
  email: string | null;
  website: string | null;
  canonical_domain: string | null;
  google_place_id: string | null;
  rating: number | null;
  review_count: number | null;
  status: ProspectStatus;
  quality_status: "OK" | "REVIEW" | "REJECTED";
  record_kind: "REAL" | "MOCK" | "TEST";
  last_researched_at: string | null;
  last_evaluated_at: string | null;
  created_at: string;
  updated_at: string;
  evaluation?: {
    score_total: number | null;
    is_opportunity: boolean | null;
    commercial_potential: string | null;
  } | null;
}

export interface ProspectDetail extends Prospect {
  sources: {
    provider: string;
    source_url: string | null;
    search_query: string | null;
    collected_at: string | null;
  }[];
  contacts: {
    channel: string;
    value: string;
    data_origin: string;
    source_url: string | null;
    verified: boolean;
  }[];
  provider_metadata: Record<string, unknown>;
}

export type Confidence = "CONFIRMED" | "LIKELY" | "POSSIBLE" | "NOT_ENOUGH_EVIDENCE";

export interface Evidence {
  id: string;
  type: string;
  source: string;
  source_url: string | null;
  observation: string;
  confidence: number;
  data_origin: "RAW" | "NORMALIZED" | "VERIFIED" | "INFERRED";
  collected_at: string | null;
}

export interface ResearchRun {
  research_run_id: string;
  status: "RUNNING" | "COMPLETED" | "PARTIAL" | "FAILED";
  schema_version: string;
  website_status: string | null;
  website_final_url: string | null;
  sources_used: string[];
  signals: {
    website?: Record<string, unknown>;
    business?: Record<string, unknown>;
    online_presence?: Record<string, unknown>;
  };
  social_profiles: Record<string, string>;
  completed_at: string | null;
  evidence: Evidence[];
}

export interface PainPoint {
  id: string;
  category: "WEBSITE" | "AUTOMATION" | "AI" | "BUSINESS_PROCESS" | "ONLINE_PRESENCE" | "CUSTOM_SOFTWARE";
  title: string;
  description: string;
  confidence: Confidence;
  evidence_ids: string[];
}

export interface Solution {
  service_category: string;
  service_name: string;
  why_it_fits: string;
  expected_value: string;
  confidence: Confidence;
  fit_rank: number;
  pain_point_id: string | null;
}

export interface ScoreBreakdown {
  scoring_version?: string;
  problem_severity: number;
  business_value: number;
  evidence_confidence: number;
  solution_fit: number;
  contactability: number;
  total: number;
  max_total: number;
  reasons: Record<string, string>;
}

export interface EvaluationRun {
  evaluation_run_id: string;
  prompt_version: string;
  scoring_version: string;
  model: string | null;
  status: string;
  is_opportunity: boolean | null;
  opportunity_summary: string | null;
  opportunity_reasoning: string | null;
  commercial_potential: "LOW" | "MEDIUM" | "HIGH" | "UNKNOWN" | null;
  score: ScoreBreakdown | Record<string, never>;
  pain_points: PainPoint[];
  solutions: Solution[];
  completed_at: string | null;
}

export type OutreachStatus =
  | "DRAFTED"
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "REJECTED"
  | "SENT"
  | "NOT_CONFIGURED"
  | "BLOCKED_DUPLICATE";

export interface OutreachMessage {
  id: string;
  prospect_id: string;
  business_name?: string;
  channel: "EMAIL" | "WHATSAPP";
  status: OutreachStatus;
  subject: string | null;
  body: string;
  to_address: string | null;
  strategy: Record<string, unknown>;
  evidence_ids: string[];
  follow_up_count: number;
  next_follow_up_at: string | null;
  sent_at: string | null;
  events: { type: string; detail: Record<string, unknown>; at: string | null }[];
  created_at: string;
}

export interface DashboardHealth {
  components: Record<string, string>;
  env: string;
  capabilities: Record<string, boolean>;
}

export interface DashboardStats {
  prospects: {
    total: number;
    by_status: Record<string, number>;
    new: number;
    researching: number;
    evaluating: number;
    evaluated: number;
    outreach_ready: number;
    contacted: number;
  };
  opportunities: { high: number; evaluations_total: number };
  outreach: {
    by_status: Record<string, number>;
    awaiting_approval: number;
    approved: number;
    sent: number;
  };
  jobs: { by_status: Record<string, number>; active: number; failed: number };
}

export interface ActivityEvent {
  at: string;
  kind: "audit" | "outreach" | "job";
  actor?: string;
  message: string;
  entity_type: string;
  entity_id: string;
  detail: Record<string, unknown>;
}

export interface ProviderAnalytics {
  provider: string;
  runs: number;
  results: number;
  success_rate: number | null;
  avg_duration_ms: number | null;
  failed: number;
  skipped: number;
}

export interface DashboardSettings {
  app_env: string;
  groq_model: string;
  max_queries_per_plan: number;
  discovery_provider_concurrency: number;
  research_concurrency: number;
  research_http_timeout_seconds: number;
  research_cache_ttl_seconds: number;
  playwright_enabled: boolean;
  worker_job_lease_seconds: number;
  embedded_worker: boolean;
  capabilities: Record<string, boolean>;
}

export interface ProfileResponse {
  business: {
    id: string;
    name: string;
    industry: string | null;
    location: { city: string | null; country: string | null; address: string | null };
    website: string | null;
    contact: { phone: string | null; email: string | null };
    rating: number | null;
    review_count: number | null;
    status: string;
    quality_status: string;
  };
  discovery: { sources: { provider: string; query: string | null; url: string | null }[] };
  research: {
    website_status: string | null;
    signals: ResearchRun["signals"];
    social_profiles: Record<string, string>;
    evidence: Evidence[];
  } | null;
  evaluation: EvaluationRun | null;
  outreach: { id: string; channel: string; status: string; subject: string | null; created_at: string }[];
}
