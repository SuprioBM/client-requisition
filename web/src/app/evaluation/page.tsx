"use client";

import { PageHeader } from "@/components/shared/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ProspectsTable } from "@/components/prospects/prospects-table";
import { useStats } from "@/lib/query/hooks";

export default function EvaluationPage() {
  const { data } = useStats();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Evaluation"
        description="Evaluated prospects ranked by opportunity score."
      />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          ["Evaluations", data?.opportunities.evaluations_total],
          ["High opportunity (≥70)", data?.opportunities.high],
          ["Evaluated prospects", data?.prospects.evaluated],
          ["Outreach ready", data?.prospects.outreach_ready],
        ].map(([label, value]) => (
          <Card key={String(label)} className="p-3.5">
            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums">{value ?? "—"}</p>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Evaluated Prospects · by score</CardTitle>
        </CardHeader>
        <CardContent>
          <ProspectsTable filters={{ status: "EVALUATED", sort: "score", limit: 50 }} />
        </CardContent>
      </Card>
    </div>
  );
}
