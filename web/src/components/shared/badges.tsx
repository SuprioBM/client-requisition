import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Confidence, JobStatus, OutreachStatus, ProspectStatus } from "@/lib/api/types";

const JOB_VARIANT: Record<JobStatus, Parameters<typeof Badge>[0]["variant"]> = {
  QUEUED: "neutral",
  RUNNING: "running",
  COMPLETED: "success",
  COMPLETED_WITH_WARNINGS: "warning",
  FAILED: "error",
  CANCELLED: "neutral",
};

export function JobStatusBadge({ status }: { status: JobStatus }) {
  return (
    <Badge variant={JOB_VARIANT[status] ?? "neutral"} className="font-mono">
      {status === "RUNNING" && (
        <span className="mr-0.5 inline-block h-1.5 w-1.5 animate-pulse-subtle rounded-full bg-running" />
      )}
      {status.replace(/_/g, " ").toLowerCase()}
    </Badge>
  );
}

const PROSPECT_VARIANT: Partial<Record<ProspectStatus, Parameters<typeof Badge>[0]["variant"]>> = {
  DISCOVERED: "neutral",
  RESEARCHING: "running",
  RESEARCHED: "info",
  EVALUATING: "running",
  EVALUATED: "info",
  OUTREACH_DRAFTED: "warning",
  OUTREACH_APPROVED: "success",
  CONTACTED: "success",
  REJECTED: "error",
  ARCHIVED: "neutral",
};

export function ProspectStatusBadge({ status }: { status: ProspectStatus }) {
  return (
    <Badge variant={PROSPECT_VARIANT[status] ?? "neutral"}>
      {status.replace(/_/g, " ").toLowerCase()}
    </Badge>
  );
}

const OUTREACH_VARIANT: Record<OutreachStatus, Parameters<typeof Badge>[0]["variant"]> = {
  DRAFTED: "neutral",
  PENDING_APPROVAL: "warning",
  APPROVED: "success",
  REJECTED: "error",
  SENT: "success",
  NOT_CONFIGURED: "neutral",
  BLOCKED_DUPLICATE: "error",
};

export function OutreachStatusBadge({ status }: { status: OutreachStatus }) {
  return (
    <Badge variant={OUTREACH_VARIANT[status] ?? "neutral"}>
      {status.replace(/_/g, " ").toLowerCase()}
    </Badge>
  );
}

const CONFIDENCE_VARIANT: Record<Confidence, Parameters<typeof Badge>[0]["variant"]> = {
  CONFIRMED: "success",
  LIKELY: "info",
  POSSIBLE: "warning",
  NOT_ENOUGH_EVIDENCE: "neutral",
};

export function ConfidenceBadge({ confidence }: { confidence: Confidence }) {
  return (
    <Badge variant={CONFIDENCE_VARIANT[confidence] ?? "neutral"}>
      {confidence.replace(/_/g, " ").toLowerCase()}
    </Badge>
  );
}

/** Numeric evidence confidence (0-1) -> qualitative label. */
export function EvidenceConfidence({ value }: { value: number }) {
  const label = value >= 0.8 ? "high" : value >= 0.55 ? "medium" : value >= 0.35 ? "low" : "very low";
  const variant = value >= 0.8 ? "success" : value >= 0.55 ? "info" : "neutral";
  return (
    <Badge variant={variant}>
      {label} · {value.toFixed(2)}
    </Badge>
  );
}

export function ScoreBadge({ score, max = 100 }: { score: number | null | undefined; max?: number }) {
  if (score === null || score === undefined) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }
  const pct = score / max;
  const color =
    pct >= 0.75
      ? "text-success"
      : pct >= 0.5
        ? "text-info"
        : pct >= 0.3
          ? "text-warning"
          : "text-muted-foreground";
  return <span className={cn("font-mono text-sm font-semibold tabular-nums", color)}>{score}</span>;
}

export function CommercialBadge({ value }: { value: string | null | undefined }) {
  if (!value) return <span className="text-xs text-muted-foreground">unknown</span>;
  const v =
    value === "HIGH" ? "success" : value === "MEDIUM" ? "info" : value === "LOW" ? "neutral" : "neutral";
  return <Badge variant={v}>{value.toLowerCase()} potential</Badge>;
}

/** Website analysis tri-state indicator: found / not detected / unknown. */
export function DetectionIndicator({
  state,
  label,
}: {
  state: boolean | null | undefined;
  label: string;
}) {
  let text: string;
  let cls: string;
  if (state === true) {
    text = "✓ Found";
    cls = "text-success";
  } else if (state === false) {
    text = "— Not detected";
    cls = "text-muted-foreground";
  } else {
    text = "? Unknown";
    cls = "text-warning";
  }
  return (
    <div className="flex items-center justify-between gap-4 py-1 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("font-medium", cls)}>{text}</span>
    </div>
  );
}
