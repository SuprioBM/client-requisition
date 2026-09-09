"use client";

import { Info } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { CommercialBadge } from "@/components/shared/badges";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { EvaluationRun, ScoreBreakdown } from "@/lib/api/types";

const DIMENSIONS: { key: keyof ScoreBreakdown; label: string; max: number }[] = [
  { key: "problem_severity", label: "Problem Severity", max: 25 },
  { key: "business_value", label: "Business Value", max: 25 },
  { key: "evidence_confidence", label: "Evidence Confidence", max: 20 },
  { key: "solution_fit", label: "Solution Fit", max: 20 },
  { key: "contactability", label: "Contactability", max: 10 },
];

export function OpportunityScore({ evaluation }: { evaluation: EvaluationRun }) {
  const score = evaluation.score as ScoreBreakdown;
  const hasScore = score && typeof score.total === "number";
  const total = hasScore ? score.total : null;
  const pct = total !== null ? total / (score.max_total ?? 100) : 0;
  const ring =
    pct >= 0.75 ? "text-success" : pct >= 0.5 ? "text-info" : pct >= 0.3 ? "text-warning" : "text-muted-foreground";

  return (
    <div className="grid gap-6 md:grid-cols-[200px_1fr]">
      <div className="flex flex-col items-center justify-center gap-2 rounded-lg border p-4">
        <div className="relative flex h-32 w-32 items-center justify-center">
          <svg viewBox="0 0 36 36" className="h-32 w-32 -rotate-90">
            <path
              className="stroke-secondary"
              strokeWidth="3"
              fill="none"
              d="M18 2.5 a 15.5 15.5 0 0 1 0 31 a 15.5 15.5 0 0 1 0 -31"
            />
            <path
              className={cn("transition-all", ring)}
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="round"
              fill="none"
              strokeDasharray={`${pct * 97.4} 97.4`}
              d="M18 2.5 a 15.5 15.5 0 0 1 0 31 a 15.5 15.5 0 0 1 0 -31"
            />
          </svg>
          <div className="absolute text-center">
            <p className={cn("text-3xl font-semibold tabular-nums", ring)}>{total ?? "—"}</p>
            <p className="text-[10px] uppercase text-muted-foreground">/ {score?.max_total ?? 100}</p>
          </div>
        </div>
        <div className="flex flex-col items-center gap-1">
          <Badge variant={evaluation.is_opportunity ? "success" : "error"}>
            {evaluation.is_opportunity ? "opportunity" : "not an opportunity"}
          </Badge>
          <CommercialBadge value={evaluation.commercial_potential} />
        </div>
      </div>

      <div className="space-y-2.5">
        {DIMENSIONS.map((d) => {
          const val = (score?.[d.key] as number | undefined) ?? 0;
          const reason = score?.reasons?.[d.key];
          return (
            <div key={d.key}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="flex items-center gap-1 text-muted-foreground">
                  {d.label}
                  {reason && (
                    <Tooltip>
                      <TooltipTrigger>
                        <Info className="h-3 w-3" />
                      </TooltipTrigger>
                      <TooltipContent>
                        <p className="font-medium">{d.label}: {val}/{d.max}</p>
                        <p className="mt-0.5 text-muted-foreground">{reason}</p>
                      </TooltipContent>
                    </Tooltip>
                  )}
                </span>
                <span className="font-mono tabular-nums">
                  {val} / {d.max}
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
                <div
                  className={cn("h-full rounded-full", ring.replace("text-", "bg-"))}
                  style={{ width: `${(val / d.max) * 100}%` }}
                />
              </div>
            </div>
          );
        })}
        {!hasScore && (
          <p className="text-xs text-muted-foreground">
            This evaluation did not produce a numeric score (status: {evaluation.status}).
          </p>
        )}
      </div>
    </div>
  );
}
