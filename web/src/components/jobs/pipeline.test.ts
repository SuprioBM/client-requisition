import { describe, expect, it } from "vitest";
import { stageStates } from "./pipeline";
import type { Job } from "@/lib/api/types";

const base: Job = {
  id: "j1",
  job_type: "DISCOVERY",
  status: "RUNNING",
  params: {},
  current_stage: null,
  progress: {},
  result: {},
  warnings: [],
  error_code: null,
  error_message: null,
  retry_count: 0,
  prospect_id: null,
  started_at: null,
  completed_at: null,
  created_at: "2026-09-09T00:00:00Z",
  updated_at: "2026-09-09T00:00:00Z",
};

describe("stageStates", () => {
  it("marks earlier stages completed and current stage running", () => {
    const s = stageStates({ ...base, current_stage: "aggregate" });
    expect(s.validate_search).toBe("completed");
    expect(s.plan_queries).toBe("completed");
    expect(s.aggregate).toBe("running");
    expect(s.save).toBe("pending");
  });

  it("marks all stages completed for a completed job", () => {
    const s = stageStates({ ...base, status: "COMPLETED", current_stage: "COMPLETED" });
    expect(Object.values(s).every((v) => v === "completed")).toBe(true);
  });

  it("marks a skipped provider from provider_runs", () => {
    const s = stageStates({
      ...base,
      status: "COMPLETED",
      result: {
        provider_runs: [{ provider: "brave", status: "skipped" } as never],
      },
    });
    expect(s.brave_discovery).toBe("skipped");
  });

  it("marks a failed provider", () => {
    const s = stageStates({
      ...base,
      current_stage: "brave_discovery",
      progress: { provider_runs: [{ provider: "google_places", status: "failed" } as never] },
    });
    expect(s.google_places_discovery).toBe("failed");
  });
});
