import type { Job } from "@/lib/api/types";

export const DISCOVERY_STAGES = [
  { id: "validate_search", label: "Validate Search" },
  { id: "resolve_location", label: "Resolve Location" },
  { id: "plan_queries", label: "Plan Queries" },
  { id: "google_places_discovery", label: "Google Places" },
  { id: "duckduckgo_discovery", label: "DuckDuckGo" },
  { id: "brave_discovery", label: "Brave" },
  { id: "aggregate", label: "Aggregate" },
  { id: "normalize", label: "Normalize" },
  { id: "clean", label: "Clean" },
  { id: "deduplicate", label: "Deduplicate" },
  { id: "save", label: "Save" },
];

export const EVALUATION_STAGES = [
  { id: "load_prospect", label: "Load Prospect" },
  { id: "research_business", label: "Research Business" },
  { id: "collect_evidence", label: "Collect Evidence" },
  { id: "detect_pain_points", label: "Detect Pain Points" },
  { id: "map_solutions", label: "Map Solutions" },
  { id: "evaluate_opportunity", label: "Evaluate Opportunity" },
  { id: "score_lead", label: "Score Lead" },
  { id: "finalize_evaluation", label: "Finalize Evaluation" },
  { id: "generate_outreach_strategy", label: "Outreach Strategy" },
  { id: "generate_email", label: "Generate Email" },
  { id: "generate_whatsapp", label: "Generate WhatsApp" },
  { id: "persist_outreach", label: "Persist Outreach" },
  { id: "human_approval", label: "Human Approval" },
];

export const RESEARCH_STAGES = [{ id: "RESEARCHING", label: "Researching website" }];

export type StageState = "completed" | "running" | "pending" | "failed" | "skipped";

export function stagesFor(job: Job) {
  if (job.job_type === "DISCOVERY") return DISCOVERY_STAGES;
  if (job.job_type === "EVALUATION") return EVALUATION_STAGES;
  return RESEARCH_STAGES;
}

export function stageStates(job: Job): Record<string, StageState> {
  const stages = stagesFor(job);
  const current = job.current_stage ?? job.progress?.stage ?? null;
  const currentIdx = stages.findIndex((s) => s.id === current);
  const terminal = ["COMPLETED", "COMPLETED_WITH_WARNINGS", "FAILED", "CANCELLED"].includes(
    job.status,
  );
  const failed = job.status === "FAILED";

  const runs: Record<string, string> = {};
  const providerRuns =
    (job.progress?.provider_runs as { provider: string; status: string }[] | undefined) ??
    (job.result?.provider_runs as { provider: string; status: string }[] | undefined) ??
    [];
  for (const r of providerRuns) {
    const key = `${r.provider}_discovery`;
    // a provider is "skipped" only if all its runs are skipped
    if (runs[key] !== "ok" && runs[key] !== "partial" && runs[key] !== "failed") {
      runs[key] = r.status;
    }
    if (["ok", "partial"].includes(r.status)) runs[key] = "ok";
    else if (r.status === "failed" && runs[key] !== "ok") runs[key] = "failed";
  }

  const out: Record<string, StageState> = {};
  stages.forEach((s, i) => {
    if (runs[s.id] === "skipped") {
      out[s.id] = "skipped";
      return;
    }
    if (runs[s.id] === "failed") {
      out[s.id] = "failed";
      return;
    }
    if (terminal && !failed) {
      out[s.id] = "completed";
      return;
    }
    if (failed) {
      if (currentIdx === -1) out[s.id] = i === 0 ? "failed" : "pending";
      else if (i < currentIdx) out[s.id] = "completed";
      else if (i === currentIdx) out[s.id] = "failed";
      else out[s.id] = "pending";
      return;
    }
    if (currentIdx === -1) {
      out[s.id] = "pending";
      return;
    }
    out[s.id] = i < currentIdx ? "completed" : i === currentIdx ? "running" : "pending";
  });
  return out;
}
