"use client";

import { ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { EvidenceConfidence } from "@/components/shared/badges";
import { EmptyState } from "@/components/shared/states";
import { formatDateTime, safeExternalUrl } from "@/lib/utils";
import type { Evidence } from "@/lib/api/types";

export function EvidenceList({
  evidence,
  highlightIds,
}: {
  evidence: Evidence[];
  highlightIds?: string[];
}) {
  if (!evidence.length) {
    return (
      <EmptyState
        title="No evidence collected"
        description="Run research to gather objective, sourced observations about this business."
      />
    );
  }
  const hl = new Set(highlightIds ?? []);
  return (
    <div className="space-y-2">
      {evidence.map((e) => (
        <div
          key={e.id}
          className={`rounded-lg border p-3 ${hl.has(e.id) ? "border-info/50 bg-info/5" : ""}`}
        >
          <div className="mb-1.5 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Badge variant="neutral" className="font-mono text-[10px]">
                {(e.type ?? "evidence").replace(/_/g, " ").toLowerCase()}
              </Badge>
              <Badge variant="outline" className="text-[10px]">
                {(e.data_origin ?? "verified").toLowerCase()}
              </Badge>
            </div>
            <EvidenceConfidence value={e.confidence ?? 0} />
          </div>
          <p className="text-sm">{e.observation}</p>
          <div className="mt-1.5 flex items-center gap-3 text-[11px] text-muted-foreground">
            <span>{e.source ?? "—"}</span>
            {safeExternalUrl(e.source_url) && (
              <a
                href={safeExternalUrl(e.source_url)!}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-0.5 text-info hover:underline"
              >
                source <ExternalLink className="h-3 w-3" />
              </a>
            )}
            <span>{formatDateTime(e.collected_at)}</span>
            <span className="font-mono opacity-60">{(e.id ?? "").slice(0, 8)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
