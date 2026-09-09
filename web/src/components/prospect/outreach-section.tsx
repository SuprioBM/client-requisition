"use client";

import Link from "next/link";
import { Mail, MessageCircle, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { OutreachStatusBadge } from "@/components/shared/badges";
import { QueryBoundary, EmptyState } from "@/components/shared/states";
import { useGenerateOutreach, useProspectOutreach } from "@/lib/query/hooks";

export function OutreachSection({
  prospectId,
  canGenerate,
}: {
  prospectId: string;
  canGenerate: boolean;
}) {
  const query = useProspectOutreach(prospectId);
  const generate = useGenerateOutreach(prospectId);

  return (
    <QueryBoundary
      query={query}
      isEmpty={(d) => d.length === 0}
      empty={
        canGenerate ? (
          <EmptyState
            icon={Sparkles}
            title="No outreach drafts yet"
            description="Generate an evidence-backed email + WhatsApp draft for this opportunity."
            action={
              <Button
                size="sm"
                onClick={() => generate.mutate()}
                disabled={generate.isPending}
              >
                {generate.isPending ? "Generating…" : "Generate outreach"}
              </Button>
            }
          />
        ) : (
          <EmptyState
            title="Evaluate first"
            description="Outreach drafts are generated from the evaluation. Evaluate this prospect to enable outreach."
          />
        )
      }
    >
      {(messages) => (
        <div className="space-y-3">
          <div className="flex justify-end">
            <Button
              size="sm"
              variant="outline"
              onClick={() => generate.mutate()}
              disabled={generate.isPending}
            >
              {generate.isPending ? "Generating…" : "Regenerate drafts"}
            </Button>
          </div>
          {messages.map((m) => (
            <div key={m.id} className="rounded-lg border p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-sm font-medium">
                  {m.channel === "EMAIL" ? (
                    <Mail className="h-3.5 w-3.5" />
                  ) : (
                    <MessageCircle className="h-3.5 w-3.5" />
                  )}
                  {m.channel}
                </span>
                <OutreachStatusBadge status={m.status} />
              </div>
              {m.subject && <p className="mb-1 text-sm font-medium">{m.subject}</p>}
              <p className="line-clamp-3 whitespace-pre-wrap text-xs text-muted-foreground">
                {m.body}
              </p>
              <Button asChild size="sm" variant="link" className="mt-1 h-auto p-0">
                <Link href={`/outreach/${m.id}`}>Review & approve →</Link>
              </Button>
            </div>
          ))}
        </div>
      )}
    </QueryBoundary>
  );
}
