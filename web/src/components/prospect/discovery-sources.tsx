"use client";

import { ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/shared/states";
import { safeExternalUrl } from "@/lib/utils";
import type { ProfileResponse } from "@/lib/api/types";

export function DiscoverySources({
  sources,
}: {
  sources: ProfileResponse["discovery"]["sources"];
}) {
  if (!sources.length) {
    return <EmptyState title="No discovery sources recorded" />;
  }
  return (
    <div className="space-y-2">
      {sources.map((s, i) => (
        <div key={i} className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
          <div className="flex items-center gap-2">
            <Badge variant="neutral">{s.provider.replace(/_/g, " ")}</Badge>
            {s.query && <span className="text-xs text-muted-foreground">“{s.query}”</span>}
          </div>
          {safeExternalUrl(s.url) && (
            <a
              href={safeExternalUrl(s.url)!}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-0.5 text-xs text-info hover:underline"
            >
              source <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      ))}
    </div>
  );
}
