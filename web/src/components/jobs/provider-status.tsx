"use client";

import { Check, MinusCircle, TriangleAlert, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Job, ProviderRun } from "@/lib/api/types";

export function ProviderStatus({ job }: { job: Job }) {
  const runs: ProviderRun[] =
    ((job.progress?.provider_runs as ProviderRun[] | undefined) ??
      (job.result?.provider_runs as ProviderRun[] | undefined) ??
      []) as ProviderRun[];

  if (job.job_type !== "DISCOVERY") return null;

  // collapse per provider
  const byProvider = new Map<
    string,
    { status: string; results: number; error?: string | null; duration: number }
  >();
  for (const r of runs) {
    const cur = byProvider.get(r.provider) ?? {
      status: "skipped",
      results: 0,
      duration: 0,
      error: null,
    };
    cur.results += r.result_count ?? 0;
    cur.duration += r.duration_ms ?? 0;
    if (["ok", "partial"].includes(r.status)) cur.status = cur.status === "failed" ? "partial" : r.status;
    else if (r.status === "failed" && cur.status !== "ok") {
      cur.status = "failed";
      cur.error = r.error_code;
    }
    byProvider.set(r.provider, cur);
  }

  const known = ["google_places", "duckduckgo", "brave", "tavily"];
  for (const k of known) if (!byProvider.has(k)) byProvider.set(k, { status: "unused", results: 0, duration: 0 });

  const meta: Record<
    string,
    { icon: React.ComponentType<{ className?: string }>; cls: string; label: string }
  > = {
    ok: { icon: Check, cls: "text-success", label: "Completed" },
    partial: { icon: TriangleAlert, cls: "text-warning", label: "Partial" },
    failed: { icon: X, cls: "text-destructive", label: "Failed" },
    skipped: { icon: MinusCircle, cls: "text-muted-foreground", label: "Not configured" },
    unused: { icon: MinusCircle, cls: "text-muted-foreground/50", label: "Not used" },
  };

  return (
    <div className="space-y-2">
      {[...byProvider.entries()].map(([provider, info]) => {
        const m = meta[info.status] ?? meta.unused;
        const Icon = m.icon;
        return (
          <div
            key={provider}
            className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
          >
            <div className="flex items-center gap-2">
              <Icon className={cn("h-4 w-4", m.cls)} />
              <span className="font-medium capitalize">{provider.replace(/_/g, " ")}</span>
            </div>
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span className={m.cls}>{m.label}</span>
              {info.status !== "unused" && info.status !== "skipped" && (
                <span className="font-mono">{info.results} results</span>
              )}
              {info.error && <span className="font-mono text-destructive">{info.error}</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
