"use client";

import { useState } from "react";
import { TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRetryJob } from "@/lib/query/hooks";
import type { Job } from "@/lib/api/types";

const RETRYABLE = new Set([
  "PROVIDER_TIMEOUT",
  "PROVIDER_RATE_LIMITED",
  "PROVIDER_UNAVAILABLE",
  "WEBSITE_TIMEOUT",
  "PLAYWRIGHT_FAILED",
  "DATABASE_ERROR",
  "REDIS_ERROR",
  "LLM_TIMEOUT",
  "LLM_RATE_LIMITED",
  "LLM_UNAVAILABLE",
  "INTERNAL_ERROR",
  "JOB_FAILED",
]);

export function JobErrorPanel({ job }: { job: Job }) {
  const [showTech, setShowTech] = useState(false);
  const retry = useRetryJob();
  if (job.status !== "FAILED") return null;

  const partial = job.result ?? {};
  const canRetry = job.error_code ? RETRYABLE.has(job.error_code) : true;

  return (
    <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4">
      <div className="flex items-start gap-3">
        <TriangleAlert className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
        <div className="min-w-0 flex-1 space-y-3">
          <div>
            <p className="font-medium text-destructive">
              {job.job_type} job encountered a problem
            </p>
          </div>
          <dl className="grid grid-cols-[100px_1fr] gap-x-3 gap-y-1 text-sm">
            <dt className="text-muted-foreground">Stage</dt>
            <dd className="font-mono">{job.current_stage ?? "—"}</dd>
            <dt className="text-muted-foreground">Error</dt>
            <dd className="font-mono text-destructive">{job.error_code ?? "UNKNOWN"}</dd>
            <dt className="text-muted-foreground">Detail</dt>
            <dd className="break-words">{job.error_message ?? "—"}</dd>
            <dt className="text-muted-foreground">Retries</dt>
            <dd>{job.retry_count}</dd>
          </dl>

          {Object.keys(partial).length > 0 && (
            <div className="rounded-md bg-background/60 p-2 text-xs">
              <p className="mb-1 font-medium">Completed before failure — partial results preserved:</p>
              <ul className="space-y-0.5 text-muted-foreground">
                {partial.prospects_created != null && (
                  <li>{String(partial.prospects_created)} prospects saved</li>
                )}
                {partial.unique_clusters != null && (
                  <li>{String(partial.unique_clusters)} unique after dedupe</li>
                )}
                {partial.raw_candidates != null && (
                  <li>{String(partial.raw_candidates)} raw candidates discovered</li>
                )}
              </ul>
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            {canRetry && (
              <Button
                size="sm"
                onClick={() => retry.mutate(job.id)}
                disabled={retry.isPending}
              >
                {retry.isPending ? "Retrying…" : "Retry job"}
              </Button>
            )}
            <Button size="sm" variant="ghost" onClick={() => setShowTech((v) => !v)}>
              {showTech ? "Hide" : "View"} technical details
            </Button>
          </div>

          {showTech && (
            <pre className="max-h-64 overflow-auto rounded-md border bg-background p-2 text-[11px] scrollbar-thin">
              {JSON.stringify(
                {
                  job_id: job.id,
                  error_code: job.error_code,
                  error_message: job.error_message,
                  current_stage: job.current_stage,
                  params: job.params,
                  started_at: job.started_at,
                  completed_at: job.completed_at,
                },
                null,
                2,
              )}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}
