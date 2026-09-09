"use client";

import { use } from "react";
import Link from "next/link";
import { ArrowLeft, Ban, RotateCw, Wifi, WifiOff } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { KeyValue } from "@/components/shared/section";
import { QueryBoundary } from "@/components/shared/states";
import { JobStatusBadge } from "@/components/shared/badges";
import { JobProgress } from "@/components/jobs/job-progress";
import { ProviderStatus } from "@/components/jobs/provider-status";
import { JobErrorPanel } from "@/components/jobs/job-error-panel";
import { useCancelJob, useJob, useRetryJob } from "@/lib/query/hooks";
import { useJobStream } from "@/lib/realtime/use-job-stream";
import { durationBetween, formatDateTime } from "@/lib/utils";

export default function JobMonitorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const query = useJob(id, { poll: true });
  const { state: streamState } = useJobStream(id);
  const retry = useRetryJob();
  const cancel = useCancelJob();

  return (
    <div className="space-y-4">
      <Link href="/jobs" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-3 w-3" /> All jobs
      </Link>

      <QueryBoundary query={query}>
        {(job) => {
          const p = job.params as Record<string, string>;
          const terminal = ["COMPLETED", "COMPLETED_WITH_WARNINGS", "FAILED", "CANCELLED"].includes(
            job.status,
          );
          const result = job.result as Record<string, unknown>;
          return (
            <>
              <PageHeader
                title={
                  job.job_type === "DISCOVERY"
                    ? `Discovery · ${p.city ?? ""} · ${p.industry ?? ""}`
                    : `${job.job_type[0]}${job.job_type.slice(1).toLowerCase()} job`
                }
                description={
                  <span className="inline-flex items-center gap-1.5 font-mono text-xs">
                    {id}
                    {streamState === "open" ? (
                      <span className="inline-flex items-center gap-1 text-success">
                        <Wifi className="h-3 w-3" /> live
                      </span>
                    ) : streamState === "error" ? (
                      <span className="inline-flex items-center gap-1 text-warning">
                        <WifiOff className="h-3 w-3" /> polling
                      </span>
                    ) : null}
                  </span>
                }
                action={
                  <div className="flex gap-2">
                    {job.status === "FAILED" && (
                      <Button size="sm" onClick={() => retry.mutate(id)} disabled={retry.isPending}>
                        <RotateCw className="h-3.5 w-3.5" /> Retry
                      </Button>
                    )}
                    {!terminal && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => cancel.mutate(id)}
                        disabled={cancel.isPending}
                      >
                        <Ban className="h-3.5 w-3.5" /> Cancel
                      </Button>
                    )}
                  </div>
                }
              />

              <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
                <div className="space-y-4">
                  <Card>
                    <CardHeader className="flex-row items-center justify-between">
                      <CardTitle>Pipeline</CardTitle>
                      <JobStatusBadge status={job.status} />
                    </CardHeader>
                    <CardContent>
                      <JobProgress job={job} />
                    </CardContent>
                  </Card>

                  {job.job_type === "DISCOVERY" && (
                    <Card>
                      <CardHeader>
                        <CardTitle>Providers</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <ProviderStatus job={job} />
                      </CardContent>
                    </Card>
                  )}

                  <JobErrorPanel job={job} />

                  {terminal && job.status !== "FAILED" && (
                    <Card>
                      <CardHeader>
                        <CardTitle>Result</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        <KeyValue
                          rows={Object.entries(result)
                            .filter(
                              ([k, v]) =>
                                typeof v !== "object" &&
                                !["prospect_ids", "resolved_location"].includes(k),
                            )
                            .map(([k, v]) => [
                              k.replace(/_/g, " "),
                              <span key={k} className="font-mono">
                                {String(v)}
                              </span>,
                            ])}
                        />
                        {job.job_type === "DISCOVERY" && (
                          <Button asChild size="sm">
                            <Link href="/prospects">View prospects</Link>
                          </Button>
                        )}
                        {job.prospect_id && (
                          <Button asChild size="sm">
                            <Link href={`/prospects/${job.prospect_id}`}>View prospect</Link>
                          </Button>
                        )}
                        {(job.warnings as string[])?.length > 0 && (
                          <div className="rounded-md bg-warning/10 p-2 text-xs text-warning">
                            {(job.warnings as string[]).map((w, i) => (
                              <p key={i}>{w}</p>
                            ))}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  )}
                </div>

                <Card className="h-fit">
                  <CardHeader>
                    <CardTitle>Job Details</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <KeyValue
                      rows={[
                        ["Type", job.job_type],
                        ["Status", <JobStatusBadge key="s" status={job.status} />],
                        ["Stage", <span key="st" className="font-mono">{job.current_stage ?? "—"}</span>],
                        ["Retries", String(job.retry_count)],
                        ["Started", formatDateTime(job.started_at)],
                        ["Completed", formatDateTime(job.completed_at)],
                        ["Duration", durationBetween(job.started_at, job.completed_at)],
                        [
                          "Input",
                          <pre key="p" className="whitespace-pre-wrap text-[11px]">
                            {JSON.stringify(job.params, null, 1)}
                          </pre>,
                        ],
                      ]}
                    />
                  </CardContent>
                </Card>
              </div>
            </>
          );
        }}
      </QueryBoundary>
    </div>
  );
}
