"use client";

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { toast } from "sonner";
import * as api from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { qk } from "./keys";

const TERMINAL = ["COMPLETED", "COMPLETED_WITH_WARNINGS", "FAILED", "CANCELLED"];

// ---------------- dashboard ----------------
export const useHealth = () =>
  useQuery({ queryKey: qk.health, queryFn: api.getHealth, refetchInterval: 15_000 });

export const useStats = () =>
  useQuery({ queryKey: qk.stats, queryFn: api.getStats, refetchInterval: 10_000 });

export const useActivity = (limit = 40) =>
  useQuery({
    queryKey: qk.activity(limit),
    queryFn: () => api.getActivity(limit),
    refetchInterval: 8_000,
  });

export const useProviderAnalytics = () =>
  useQuery({ queryKey: qk.providerAnalytics, queryFn: api.getProviderAnalytics });

export const useResearchAnalytics = () =>
  useQuery({ queryKey: qk.researchAnalytics, queryFn: api.getResearchAnalytics });

export const useSettings = () =>
  useQuery({ queryKey: qk.settings, queryFn: api.getSettings });

// ---------------- jobs ----------------
export const useJobs = (filters: Parameters<typeof api.listJobs>[0] = {}) =>
  useQuery({
    queryKey: qk.jobs(filters),
    queryFn: () => api.listJobs(filters),
    placeholderData: keepPreviousData,
    refetchInterval: (q) => {
      const items = q.state.data?.items ?? [];
      return items.some((j) => !TERMINAL.includes(j.status)) ? 3_000 : 15_000;
    },
  });

export const useJob = (id: string, opts: { poll?: boolean } = {}) =>
  useQuery({
    queryKey: qk.job(id),
    queryFn: () => api.getJob(id),
    enabled: !!id,
    refetchInterval: (q) => {
      if (!opts.poll) return false;
      const s = q.state.data?.status;
      return s && !TERMINAL.includes(s) ? 2_000 : false;
    },
  });

export function useActiveJobs() {
  return useQuery({
    queryKey: qk.jobs({ active_only: true }),
    queryFn: () => api.listJobs({ active_only: true, limit: 20 }),
    refetchInterval: (q) => ((q.state.data?.items.length ?? 0) > 0 ? 2_500 : 8_000),
  });
}

export function useRetryJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.retryJob,
    onSuccess: (job) => {
      toast.success("Job requeued");
      qc.invalidateQueries({ queryKey: qk.job(job.id) });
      qc.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: errToast,
  });
}

export function useCancelJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.cancelJob,
    onSuccess: (job) => {
      toast.message("Job cancelled");
      qc.invalidateQueries({ queryKey: qk.job(job.id) });
      qc.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: errToast,
  });
}

// ---------------- discovery ----------------
export function useStartDiscovery() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.startDiscovery,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: qk.stats });
    },
    onError: errToast,
  });
}

// ---------------- prospects ----------------
export const useProspects = (filters: Parameters<typeof api.listProspects>[0] = {}) =>
  useQuery({
    queryKey: qk.prospects(filters),
    queryFn: () => api.listProspects(filters),
    placeholderData: keepPreviousData,
  });

export const useProspect = (id: string) =>
  useQuery({ queryKey: qk.prospect(id), queryFn: () => api.getProspect(id), enabled: !!id });

export const useProfile = (id: string) =>
  useQuery({ queryKey: qk.profile(id), queryFn: () => api.getProfile(id), enabled: !!id });

// ---------------- research ----------------
export const useResearch = (id: string) =>
  useQuery({
    queryKey: qk.research(id),
    queryFn: () => api.getResearch(id),
    enabled: !!id,
    retry: (n, e) => !(e instanceof ApiError && e.status === 404) && n < 1,
  });

export function useStartResearch(prospectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (force?: boolean) => api.startResearch(prospectId, force),
    onSuccess: () => {
      toast.success("Research job queued");
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: qk.prospect(prospectId) });
    },
    onError: errToast,
  });
}

// ---------------- evaluation ----------------
export const useEvaluation = (id: string) =>
  useQuery({
    queryKey: qk.evaluation(id),
    queryFn: () => api.getEvaluation(id),
    enabled: !!id,
    retry: (n, e) => !(e instanceof ApiError && e.status === 404) && n < 1,
  });

export const useEvaluationHistory = (id: string) =>
  useQuery({
    queryKey: qk.evaluationHistory(id),
    queryFn: () => api.getEvaluationHistory(id),
    enabled: !!id,
  });

export function useStartEvaluation(prospectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.startEvaluation(prospectId),
    onSuccess: () => {
      toast.success("Evaluation job queued");
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: qk.prospect(prospectId) });
    },
    onError: errToast,
  });
}

export function useBulkResearch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[]) => api.bulkResearch(ids),
    onSuccess: (r) => {
      toast.success(`${r.queued.length} research job(s) queued`);
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["prospects"] });
    },
    onError: errToast,
  });
}

export function useBulkEvaluate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[]) => api.bulkEvaluate(ids),
    onSuccess: (r) => {
      toast.success(`${r.queued.length} evaluation job(s) queued`);
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["prospects"] });
    },
    onError: errToast,
  });
}

// ---------------- outreach ----------------
export const useOutreachList = (filters: Parameters<typeof api.listOutreach>[0] = {}) =>
  useQuery({
    queryKey: qk.outreach(filters),
    queryFn: () => api.listOutreach(filters),
    placeholderData: keepPreviousData,
    refetchInterval: 12_000,
  });

export const useOutreachItem = (id: string) =>
  useQuery({ queryKey: qk.outreachItem(id), queryFn: () => api.getOutreach(id), enabled: !!id });

export const useProspectOutreach = (id: string) =>
  useQuery({
    queryKey: qk.prospectOutreach(id),
    queryFn: () => api.listProspectOutreach(id),
    enabled: !!id,
  });

export function useGenerateOutreach(prospectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.generateOutreach(prospectId),
    onSuccess: () => {
      toast.success("Outreach drafts generated");
      qc.invalidateQueries({ queryKey: qk.prospectOutreach(prospectId) });
      qc.invalidateQueries({ queryKey: ["outreach"] });
      qc.invalidateQueries({ queryKey: qk.profile(prospectId) });
    },
    onError: errToast,
  });
}

export function useSaveOutreach(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { subject?: string; body?: string }) => api.saveOutreachDraft(id, body),
    onSuccess: () => {
      toast.success("Draft saved");
      qc.invalidateQueries({ queryKey: qk.outreachItem(id) });
      qc.invalidateQueries({ queryKey: ["outreach"] });
    },
    onError: errToast,
  });
}

export function useApproveOutreach(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (edited_body?: string) => api.approveOutreach(id, edited_body),
    onSuccess: () => {
      toast.success("Message approved");
      invalidateOutreach(qc, id);
    },
    onError: errToast,
  });
}

export function useRejectOutreach(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (reason?: string) => api.rejectOutreach(id, reason),
    onSuccess: () => {
      toast.message("Message rejected");
      invalidateOutreach(qc, id);
    },
    onError: errToast,
  });
}

export function useSendOutreach(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (override?: boolean) => api.sendOutreach(id, override),
    onSuccess: (r) => {
      if (r.status === "SENT") toast.success("Message sent");
      else if (r.status === "NOT_CONFIGURED")
        toast.warning("No sending provider configured — message not sent", {
          description: r.detail,
        });
      else toast.message(`Send result: ${r.status}`);
      invalidateOutreach(qc, id);
    },
    onError: errToast,
  });
}

// ---------------- helpers ----------------
function invalidateOutreach(qc: ReturnType<typeof useQueryClient>, id: string) {
  qc.invalidateQueries({ queryKey: qk.outreachItem(id) });
  qc.invalidateQueries({ queryKey: ["outreach"] });
  qc.invalidateQueries({ queryKey: ["prospect-outreach"] });
  qc.invalidateQueries({ queryKey: qk.stats });
}

function errToast(error: unknown) {
  const msg = error instanceof ApiError ? `${error.code}: ${error.message}` : String(error);
  toast.error("Something went wrong", { description: msg });
}
