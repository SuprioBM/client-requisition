"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { QueryBoundary } from "@/components/shared/states";
import { useHealth } from "@/lib/query/hooks";
import { cn } from "@/lib/utils";

const LABEL: Record<string, string> = {
  online: "Online",
  degraded: "Degraded",
  offline: "Offline",
  unknown: "Unknown",
};
const DOT: Record<string, string> = {
  online: "bg-success",
  degraded: "bg-warning",
  offline: "bg-destructive",
  unknown: "bg-muted-foreground",
};

export function SystemStatus() {
  const query = useHealth();
  return (
    <Card>
      <CardHeader>
        <CardTitle>System Status</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <QueryBoundary query={query}>
          {(health) => (
            <>
              <div className="grid grid-cols-2 gap-x-6 gap-y-2">
                {["api", "worker", "redis", "database"].map((c) => {
                  const s = health.components[c] ?? "unknown";
                  return (
                    <div key={c} className="flex items-center justify-between text-sm">
                      <span className="capitalize text-muted-foreground">{c}</span>
                      <span className="flex items-center gap-1.5">
                        <span className={cn("h-2 w-2 rounded-full", DOT[s])} />
                        {LABEL[s]}
                      </span>
                    </div>
                  );
                })}
              </div>
              <div className="border-t pt-3">
                <p className="mb-1.5 text-[11px] font-medium uppercase text-muted-foreground">
                  Capabilities
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(health.capabilities).map(([k, v]) => (
                    <span
                      key={k}
                      className={cn(
                        "rounded-full border px-2 py-0.5 text-[11px]",
                        v
                          ? "border-success/30 bg-success/10 text-success"
                          : "border-border bg-muted text-muted-foreground line-through",
                      )}
                    >
                      {k.replace(/_/g, " ")}
                    </span>
                  ))}
                </div>
              </div>
            </>
          )}
        </QueryBoundary>
      </CardContent>
    </Card>
  );
}
