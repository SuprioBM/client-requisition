"use client";

import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { QueryBoundary, EmptyState } from "@/components/shared/states";
import { JobProgress } from "@/components/jobs/job-progress";
import { JobStatusBadge } from "@/components/shared/badges";
import { useActiveJobs } from "@/lib/query/hooks";
import { Radar } from "lucide-react";
import { durationBetween } from "@/lib/utils";

export function ActiveJobs() {
  const query = useActiveJobs();
  return (
    <Card>
      <CardHeader>
        <CardTitle>Active Jobs</CardTitle>
      </CardHeader>
      <CardContent>
        <QueryBoundary
          query={query}
          isEmpty={(d) => d.items.length === 0}
          empty={
            <EmptyState
              icon={Radar}
              title="No jobs running"
              description="Start a discovery job to find potential clients."
              action={
                <Link
                  href="/discover"
                  className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
                >
                  Discover businesses
                </Link>
              }
              className="border-0"
            />
          }
        >
          {(data) => (
            <div className="space-y-4">
              {data.items.map((job) => {
                const p = job.params as Record<string, string>;
                const label =
                  job.job_type === "DISCOVERY"
                    ? `${p.city ?? ""} · ${p.industry ?? ""}`
                    : `${job.job_type.toLowerCase()} · ${job.prospect_id?.slice(0, 8) ?? ""}`;
                return (
                  <Link
                    key={job.id}
                    href={`/jobs/${job.id}`}
                    className="block rounded-lg border p-3 transition-colors hover:border-info/50"
                  >
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium capitalize">{label}</span>
                      <JobStatusBadge status={job.status} />
                    </div>
                    <JobProgress job={job} compact />
                    <div className="mt-2 flex items-center justify-between text-[11px] text-muted-foreground">
                      <span className="font-mono">{job.current_stage ?? "queued"}</span>
                      <span>{durationBetween(job.started_at, null)}</span>
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </QueryBoundary>
      </CardContent>
    </Card>
  );
}
