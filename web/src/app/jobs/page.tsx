"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/shared/page-header";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { JobStatusBadge } from "@/components/shared/badges";
import { QueryBoundary, EmptyState } from "@/components/shared/states";
import { useJobs } from "@/lib/query/hooks";
import { durationBetween, relativeTime } from "@/lib/utils";

const FILTERS = ["all", "QUEUED", "RUNNING", "COMPLETED", "FAILED"] as const;

export default function JobsPage() {
  const router = useRouter();
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");
  const query = useJobs(filter === "all" ? { limit: 100 } : { status: filter, limit: 100 });

  return (
    <div>
      <PageHeader title="Jobs" description="Every discovery, research and evaluation job." />

      <div className="mb-3 flex gap-1.5">
        {FILTERS.map((f) => (
          <Button
            key={f}
            size="sm"
            variant={filter === f ? "default" : "outline"}
            onClick={() => setFilter(f)}
          >
            {f.toLowerCase()}
          </Button>
        ))}
      </div>

      <div className="rounded-lg border">
        <QueryBoundary
          query={query}
          isEmpty={(d) => d.items.length === 0}
          empty={<EmptyState title="No jobs" description="Start a discovery job to see it here." className="border-0" />}
        >
          {(data) => (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Input</TableHead>
                  <TableHead>Stage</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((job) => {
                  const p = job.params as Record<string, string>;
                  return (
                    <TableRow
                      key={job.id}
                      className="cursor-pointer"
                      onClick={() => router.push(`/jobs/${job.id}`)}
                    >
                      <TableCell className="font-medium">{job.job_type.toLowerCase()}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {job.job_type === "DISCOVERY"
                          ? `${p.city ?? ""} · ${p.industry ?? ""}`
                          : (job.prospect_id?.slice(0, 12) ?? "—")}
                      </TableCell>
                      <TableCell className="font-mono text-xs">{job.current_stage ?? "—"}</TableCell>
                      <TableCell>
                        <JobStatusBadge status={job.status} />
                        {job.error_code && (
                          <span className="ml-1 font-mono text-[11px] text-destructive">
                            {job.error_code}
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-xs">
                        {durationBetween(job.started_at, job.completed_at)}
                      </TableCell>
                      <TableCell className="text-[11px] text-muted-foreground">
                        {relativeTime(job.created_at)}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </QueryBoundary>
      </div>
    </div>
  );
}
