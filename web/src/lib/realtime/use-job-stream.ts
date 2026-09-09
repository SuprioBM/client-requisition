"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { SSE_BASE } from "@/lib/api/client";
import { qk } from "@/lib/query/keys";
import type { Job } from "@/lib/api/types";

type StreamState = "connecting" | "open" | "closed" | "error";
const TERMINAL = ["COMPLETED", "COMPLETED_WITH_WARNINGS", "FAILED", "CANCELLED"];

/**
 * Subscribes to the backend SSE stream for one job and pushes every update into
 * the React Query cache. Invalidates prospect / dashboard / activity queries as
 * the job progresses, so tables update with no manual refresh. Falls back to
 * nothing special — `useJob(id, { poll:true })` still works if SSE fails.
 */
export function useJobStream(jobId: string | undefined) {
  const qc = useQueryClient();
  const [state, setState] = useState<StreamState>("connecting");
  const lastStage = useRef<string | null>(null);

  useEffect(() => {
    if (!jobId) return;
    setState("connecting");
    const es = new EventSource(`${SSE_BASE}/api/v1/jobs/${jobId}/stream`);

    es.addEventListener("open", () => setState("open"));

    const onJob = (raw: MessageEvent) => {
      let job: Job;
      try {
        job = JSON.parse(raw.data) as Job;
      } catch {
        return;
      }
      qc.setQueryData(qk.job(job.id), job);

      const stage = job.current_stage ?? job.progress?.stage ?? null;
      if (stage !== lastStage.current) {
        lastStage.current = stage;
        // a stage advanced — refresh views that depend on partial results
        qc.invalidateQueries({ queryKey: ["prospects"] });
        qc.invalidateQueries({ queryKey: qk.stats });
        qc.invalidateQueries({ queryKey: ["activity"] });
        if (job.prospect_id) {
          qc.invalidateQueries({ queryKey: qk.profile(job.prospect_id) });
          qc.invalidateQueries({ queryKey: qk.research(job.prospect_id) });
          qc.invalidateQueries({ queryKey: qk.evaluation(job.prospect_id) });
          qc.invalidateQueries({ queryKey: qk.prospectOutreach(job.prospect_id) });
        }
      }

      if (TERMINAL.includes(job.status)) {
        qc.invalidateQueries({ queryKey: ["jobs"] });
        qc.invalidateQueries({ queryKey: ["prospects"] });
        qc.invalidateQueries({ queryKey: ["outreach"] });
        qc.invalidateQueries({ queryKey: qk.stats });
      }
    };

    es.addEventListener("job", onJob);
    es.addEventListener("done", (e) => {
      onJob(e as MessageEvent);
      setState("closed");
      es.close();
    });
    es.addEventListener("error", () => {
      // EventSource auto-reconnects; surface state but don't spam
      setState((s) => (s === "closed" ? s : "error"));
    });

    return () => es.close();
  }, [jobId, qc]);

  return { state };
}
