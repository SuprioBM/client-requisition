"use client";

import { Check, CircleDashed, Loader2, MinusCircle, X } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import type { Job } from "@/lib/api/types";
import { stageStates, stagesFor, type StageState } from "./pipeline";

const ICON: Record<StageState, React.ComponentType<{ className?: string }>> = {
  completed: Check,
  running: Loader2,
  pending: CircleDashed,
  failed: X,
  skipped: MinusCircle,
};
const CLS: Record<StageState, string> = {
  completed: "text-success",
  running: "text-running",
  pending: "text-muted-foreground/40",
  failed: "text-destructive",
  skipped: "text-muted-foreground/60",
};

export function JobProgress({ job, compact }: { job: Job; compact?: boolean }) {
  const stages = stagesFor(job);
  const states = stageStates(job);
  const percent =
    typeof job.progress?.percent === "number"
      ? job.progress.percent
      : job.status === "COMPLETED" || job.status === "COMPLETED_WITH_WARNINGS"
        ? 100
        : 0;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <Progress
          value={percent}
          className="h-2"
          indicatorClassName={
            job.status === "FAILED"
              ? "bg-destructive"
              : job.status.startsWith("COMPLETED")
                ? "bg-success"
                : "bg-running"
          }
        />
        <span className="w-10 shrink-0 text-right font-mono text-xs tabular-nums text-muted-foreground">
          {percent}%
        </span>
      </div>

      {!compact && (
        <ol className="grid gap-1 text-sm sm:grid-cols-2">
          {stages.map((s) => {
            const st = states[s.id] ?? "pending";
            const Icon = ICON[st];
            return (
              <li key={s.id} className="flex items-center gap-2">
                <Icon className={cn("h-3.5 w-3.5 shrink-0", CLS[st], st === "running" && "animate-spin")} />
                <span
                  className={cn(
                    st === "pending" && "text-muted-foreground/50",
                    st === "running" && "font-medium",
                    st === "skipped" && "text-muted-foreground/70 line-through",
                  )}
                >
                  {s.label}
                </span>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
