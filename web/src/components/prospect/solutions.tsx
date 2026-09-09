"use client";

import { Badge } from "@/components/ui/badge";
import { ConfidenceBadge } from "@/components/shared/badges";
import { EmptyState } from "@/components/shared/states";
import type { Solution } from "@/lib/api/types";

export function Solutions({ solutions }: { solutions: Solution[] }) {
  if (!solutions.length) {
    return <EmptyState title="No solutions mapped" description="No available service was a credible fit for the identified pain points." />;
  }
  const sorted = [...solutions].sort((a, b) => a.fit_rank - b.fit_rank);
  return (
    <div className="space-y-2">
      {sorted.map((s, i) => (
        <div key={i} className="rounded-lg border p-3">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs text-muted-foreground">#{s.fit_rank}</span>
            <span className="font-medium">{s.service_name}</span>
            <Badge variant="outline" className="text-[10px]">
              {s.service_category}
            </Badge>
            <ConfidenceBadge confidence={s.confidence} />
          </div>
          <dl className="grid gap-1 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-[11px] uppercase text-muted-foreground">Why it fits</dt>
              <dd>{s.why_it_fits}</dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase text-muted-foreground">Potential value</dt>
              <dd>{s.expected_value}</dd>
            </div>
          </dl>
        </div>
      ))}
    </div>
  );
}
