"use client";

import { PageHeader } from "@/components/shared/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { QueryBoundary } from "@/components/shared/states";
import { ProspectsTable } from "@/components/prospects/prospects-table";
import { useProviderAnalytics, useResearchAnalytics } from "@/lib/query/hooks";

export default function ResearchPage() {
  const providers = useProviderAnalytics();
  const research = useResearchAnalytics();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Research"
        description="Website research status across prospects, and provider performance."
      />

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Discovery Provider Performance</CardTitle>
          </CardHeader>
          <CardContent>
            <QueryBoundary query={providers} isEmpty={(d) => d.length === 0}>
              {(rows) => (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase text-muted-foreground">
                      <th className="pb-1">Provider</th>
                      <th className="pb-1">Results</th>
                      <th className="pb-1">Success</th>
                      <th className="pb-1">Avg ms</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.provider} className="border-t">
                        <td className="py-1.5 capitalize">{r.provider.replace(/_/g, " ")}</td>
                        <td className="py-1.5 font-mono">{r.results}</td>
                        <td className="py-1.5">
                          {r.success_rate === null
                            ? "—"
                            : `${Math.round(r.success_rate * 100)}%`}
                        </td>
                        <td className="py-1.5 font-mono">{r.avg_duration_ms ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </QueryBoundary>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Research Runs</CardTitle>
          </CardHeader>
          <CardContent>
            <QueryBoundary query={research}>
              {(data) => {
                const d = data as {
                  total?: number;
                  by_status?: Record<string, number>;
                  by_website_status?: Record<string, number>;
                  source_usage?: Record<string, number>;
                };
                const groups: [string, Record<string, number> | undefined][] = [
                  ["by status", d.by_status],
                  ["by website status", d.by_website_status],
                  ["source usage", d.source_usage],
                ];
                return (
                  <div className="space-y-3 text-sm">
                    <p>
                      <span className="font-mono text-lg">{d.total ?? 0}</span> research runs
                    </p>
                    {groups.map(([label, obj]) => (
                      <div key={label}>
                        <p className="text-[11px] uppercase text-muted-foreground">{label}</p>
                        <div className="flex flex-wrap gap-1.5">
                          {Object.entries(obj ?? {}).map(([k, n]) => (
                            <span
                              key={k}
                              className="rounded-full bg-secondary px-2 py-0.5 text-xs"
                            >
                              {k}: {n}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                );
              }}
            </QueryBoundary>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Researched Prospects</CardTitle>
        </CardHeader>
        <CardContent>
          <ProspectsTable filters={{ status: "RESEARCHED", limit: 50, sort: "recently_researched" }} />
        </CardContent>
      </Card>
    </div>
  );
}
