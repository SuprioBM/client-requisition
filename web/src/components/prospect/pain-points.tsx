"use client";

import { Badge } from "@/components/ui/badge";
import { ConfidenceBadge } from "@/components/shared/badges";
import { EmptyState } from "@/components/shared/states";
import type { Evidence, PainPoint } from "@/lib/api/types";

export function PainPoints({
  painPoints,
  evidence,
}: {
  painPoints: PainPoint[];
  evidence: Evidence[];
}) {
  if (!painPoints.length) {
    return (
      <EmptyState
        title="No pain points identified"
        description="The evaluator only reports problems it can back with evidence. An empty list is a valid, conservative result."
      />
    );
  }
  const byId = new Map(evidence.map((e) => [e.id, e]));

  return (
    <div className="grid gap-3 md:grid-cols-2">
      {painPoints.map((pp) => {
        const supporting = pp.evidence_ids.map((id) => byId.get(id)).filter(Boolean) as Evidence[];
        return (
          <div key={pp.id} className="flex flex-col rounded-lg border p-3">
            <div className="mb-1.5 flex items-center justify-between gap-2">
              <Badge variant="neutral">{pp.category.replace(/_/g, " ").toLowerCase()}</Badge>
              <ConfidenceBadge confidence={pp.confidence} />
            </div>
            <p className="font-medium">{pp.title}</p>
            <p className="mt-1 text-sm text-muted-foreground">{pp.description}</p>
            <div className="mt-3 border-t pt-2">
              <p className="mb-1 text-[11px] font-medium uppercase text-muted-foreground">
                Evidence ({supporting.length || pp.evidence_ids.length})
              </p>
              {supporting.length ? (
                <ul className="space-y-1">
                  {supporting.map((e) => (
                    <li key={e.id} className="flex items-start gap-1.5 text-xs">
                      <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-info" />
                      <span>{e.observation}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-muted-foreground">
                  Cited: {pp.evidence_ids.map((i) => i.slice(0, 8)).join(", ") || "none"}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
