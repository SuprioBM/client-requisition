import { apiFetch } from "./client";
import type {
  ActivityEvent,
  DashboardHealth,
  DashboardSettings,
  DashboardStats,
  EvaluationRun,
  Job,
  OutreachMessage,
  Page,
  ProfileResponse,
  Prospect,
  ProspectDetail,
  ProviderAnalytics,
  ResearchRun,
} from "./types";

// ---- dashboard ----
export const getHealth = () => apiFetch<DashboardHealth>("/api/v1/dashboard/health");
export const getStats = () => apiFetch<DashboardStats>("/api/v1/dashboard/stats");
export const getActivity = (limit = 40) =>
  apiFetch<ActivityEvent[]>("/api/v1/dashboard/activity", { query: { limit } });
export const getProviderAnalytics = () =>
  apiFetch<ProviderAnalytics[]>("/api/v1/dashboard/analytics/providers");
export const getResearchAnalytics = () =>
  apiFetch<Record<string, unknown>>("/api/v1/dashboard/analytics/research");
export const getSettings = () => apiFetch<DashboardSettings>("/api/v1/dashboard/settings");

// ---- discovery ----
export type DiscoveryInput = {
  country: string;
  city: string;
  industry: string;
  radius_km: number;
  target_leads: number;
};
export const startDiscovery = (input: DiscoveryInput) =>
  apiFetch<{ job_id: string; status: string }>("/api/v1/discovery/search", {
    method: "POST",
    body: input,
  });
export const previewPlan = (input: Pick<DiscoveryInput, "country" | "city" | "industry">) =>
  apiFetch<{ queries: string[]; location_label: string }>("/api/v1/discovery/plan-preview", {
    method: "POST",
    body: { ...input, radius_km: 10, target_leads: 10 },
  });

// ---- jobs ----
export const listJobs = (params: {
  status?: string;
  job_type?: string;
  active_only?: boolean;
  limit?: number;
  offset?: number;
} = {}) => apiFetch<Page<Job>>("/api/v1/jobs", { query: params });
export const getJob = (id: string) => apiFetch<Job>(`/api/v1/jobs/${id}`);
export const retryJob = (id: string) =>
  apiFetch<Job>(`/api/v1/jobs/${id}/retry`, { method: "POST" });
export const cancelJob = (id: string) =>
  apiFetch<Job>(`/api/v1/jobs/${id}/cancel`, { method: "POST" });

// ---- prospects ----
export const listProspects = (params: {
  industry?: string;
  city?: string;
  status?: string;
  website_exists?: boolean;
  min_score?: number;
  q?: string;
  limit?: number;
  offset?: number;
  sort?: string;
} = {}) => apiFetch<Page<Prospect>>("/api/v1/prospects", { query: params });
export const getProspect = (id: string) => apiFetch<ProspectDetail>(`/api/v1/prospects/${id}`);
export const getProfile = (id: string) =>
  apiFetch<ProfileResponse>(`/api/v1/prospects/${id}/profile`);

// ---- research ----
export const getResearch = (id: string) =>
  apiFetch<ResearchRun>(`/api/v1/prospects/${id}/research`);
export const startResearch = (id: string, force = false) =>
  apiFetch<{ job_id: string; status: string }>(`/api/v1/prospects/${id}/research`, {
    method: "POST",
    query: { force },
  });
export const bulkResearch = (prospect_ids: string[], force = false) =>
  apiFetch<{ queued: { prospect_id: string; job_id: string }[] }>(
    "/api/v1/prospects/bulk/research",
    { method: "POST", body: { prospect_ids, force } },
  );

// ---- evaluation ----
export const getEvaluation = (id: string) =>
  apiFetch<EvaluationRun>(`/api/v1/prospects/${id}/evaluation`);
export const getEvaluationHistory = (id: string) =>
  apiFetch<EvaluationRun[]>(`/api/v1/prospects/${id}/evaluations`);
export const startEvaluation = (id: string) =>
  apiFetch<{ job_id: string; status: string }>(`/api/v1/prospects/${id}/evaluate`, {
    method: "POST",
  });
export const bulkEvaluate = (prospect_ids: string[]) =>
  apiFetch<{ queued: { prospect_id: string; job_id: string }[] }>(
    "/api/v1/prospects/bulk/evaluate",
    { method: "POST", body: { prospect_ids } },
  );

// ---- outreach ----
export const listOutreach = (params: {
  status?: string;
  channel?: string;
  limit?: number;
  offset?: number;
} = {}) => apiFetch<Page<OutreachMessage>>("/api/v1/outreach", { query: params });
export const listProspectOutreach = (id: string) =>
  apiFetch<OutreachMessage[]>(`/api/v1/prospects/${id}/outreach`);
export const getOutreach = (id: string) => apiFetch<OutreachMessage>(`/api/v1/outreach/${id}`);
export const generateOutreach = (prospectId: string) =>
  apiFetch<Record<string, unknown>>(`/api/v1/prospects/${prospectId}/outreach/generate`, {
    method: "POST",
  });
export const saveOutreachDraft = (id: string, body: { subject?: string; body?: string }) =>
  apiFetch<OutreachMessage>(`/api/v1/outreach/${id}`, { method: "PATCH", body });
export const approveOutreach = (id: string, edited_body?: string) =>
  apiFetch<{ id: string; status: string }>(`/api/v1/outreach/${id}/approve`, {
    method: "POST",
    body: { actor: "operator", edited_body },
  });
export const rejectOutreach = (id: string, reason?: string) =>
  apiFetch<{ id: string; status: string }>(`/api/v1/outreach/${id}/reject`, {
    method: "POST",
    body: { actor: "operator", reason },
  });
export const sendOutreach = (id: string, override_duplicate = false) =>
  apiFetch<{ id: string; status: string; detail?: string }>(`/api/v1/outreach/${id}/send`, {
    method: "POST",
    body: { actor: "operator", override_duplicate },
  });
