"use client";

import { Radar, FlaskConical, BarChart3, Mail, ShieldCheck, CircleDot } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/misc";
import { QueryBoundary, EmptyState } from "@/components/shared/states";
import { useActivity } from "@/lib/query/hooks";
import { relativeTime } from "@/lib/utils";

function iconFor(message: string) {
  if (message.includes("discovery")) return Radar;
  if (message.includes("research")) return FlaskConical;
  if (message.includes("evaluation")) return BarChart3;
  if (message.includes("outreach") || message.includes("message")) return Mail;
  if (message.includes("approved") || message.includes("sent")) return ShieldCheck;
  return CircleDot;
}

export function ActivityFeed({ limit = 30 }: { limit?: number }) {
  const query = useActivity(limit);
  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>Activity</CardTitle>
        <span className="text-[10px] uppercase text-muted-foreground">live</span>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 p-0">
        <QueryBoundary
          query={query}
          isEmpty={(d) => d.length === 0}
          empty={
            <EmptyState
              title="No activity yet"
              description="Events appear here as jobs run and prospects move through the pipeline."
              className="m-4 border-0"
            />
          }
        >
          {(events) => (
            <ScrollArea className="h-[420px]">
              <ul className="divide-y">
                {events.map((e, i) => {
                  const Icon = iconFor(e.message);
                  return (
                    <li key={i} className="flex items-start gap-3 px-4 py-2.5 animate-fade-in">
                      <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm capitalize">{e.message}</p>
                        <p className="text-[11px] text-muted-foreground">
                          {relativeTime(e.at)}
                          {e.detail?.error_code ? (
                            <span className="ml-1 font-mono text-destructive">
                              {String(e.detail.error_code)}
                            </span>
                          ) : null}
                        </p>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </ScrollArea>
          )}
        </QueryBoundary>
      </CardContent>
    </Card>
  );
}
