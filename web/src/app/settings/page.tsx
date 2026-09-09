"use client";

import { PageHeader } from "@/components/shared/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { KeyValue } from "@/components/shared/section";
import { QueryBoundary } from "@/components/shared/states";
import { useSettings } from "@/lib/query/hooks";

export default function SettingsPage() {
  const query = useSettings();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description="Non-secret runtime configuration reported by the backend. API keys are never exposed to the browser."
      />

      <QueryBoundary query={query}>
        {(s) => (
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Runtime</CardTitle>
              </CardHeader>
              <CardContent>
                <KeyValue
                  rows={[
                    ["Environment", <span key="e" className="font-mono uppercase">{s.app_env}</span>],
                    ["LLM model", <span key="m" className="font-mono">{s.groq_model}</span>],
                    ["Embedded worker", s.embedded_worker ? "yes" : "no"],
                    ["Playwright fallback", s.playwright_enabled ? "enabled" : "disabled"],
                  ]}
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Pipeline Tuning</CardTitle>
              </CardHeader>
              <CardContent>
                <KeyValue
                  rows={[
                    ["Max queries / plan", String(s.max_queries_per_plan)],
                    ["Discovery concurrency", String(s.discovery_provider_concurrency)],
                    ["Research concurrency", String(s.research_concurrency)],
                    ["HTTP timeout", `${s.research_http_timeout_seconds}s`],
                    [
                      "Research cache TTL",
                      `${Math.round(s.research_cache_ttl_seconds / 86400)} days`,
                    ],
                    ["Worker job lease", `${s.worker_job_lease_seconds}s`],
                  ]}
                />
                <p className="mt-3 text-[11px] text-muted-foreground">
                  These are configured via backend environment variables (`.env`). This page is
                  read-only.
                </p>
              </CardContent>
            </Card>

            <Card className="md:col-span-2">
              <CardHeader>
                <CardTitle>Capabilities</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(s.capabilities).map(([k, v]) => (
                    <span
                      key={k}
                      className={
                        "rounded-full border px-2.5 py-0.5 text-xs " +
                        (v
                          ? "border-success/30 bg-success/10 text-success"
                          : "border-border bg-muted text-muted-foreground line-through")
                      }
                    >
                      {k.replace(/_/g, " ")}
                    </span>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </QueryBoundary>
    </div>
  );
}
