"use client";

import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/misc";
import { useStats } from "@/lib/query/hooks";
import { cn } from "@/lib/utils";

function Kpi({
  label,
  value,
  href,
  accent,
}: {
  label: string;
  value: number | undefined;
  href: string;
  accent?: string;
}) {
  return (
    <Link href={href}>
      <Card className="p-3.5 transition-colors hover:border-info/50">
        <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
        {value === undefined ? (
          <Skeleton className="mt-1.5 h-7 w-12" />
        ) : (
          <p className={cn("mt-1 text-2xl font-semibold tabular-nums", accent)}>{value}</p>
        )}
      </Card>
    </Link>
  );
}

export function KpiGrid() {
  const { data } = useStats();
  const p = data?.prospects;
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
      <Kpi label="Total Prospects" value={p?.total} href="/prospects" />
      <Kpi label="New" value={p?.new} href="/prospects?status=DISCOVERED" />
      <Kpi label="Researching" value={p?.researching} href="/prospects?status=RESEARCHED" />
      <Kpi label="Evaluated" value={p?.evaluated} href="/prospects?status=EVALUATED" />
      <Kpi
        label="High Opportunity"
        value={data?.opportunities.high}
        href="/evaluation"
        accent="text-success"
      />
      <Kpi
        label="Awaiting Approval"
        value={data?.outreach.awaiting_approval}
        href="/outreach"
        accent="text-warning"
      />
      <Kpi label="Messages Sent" value={data?.outreach.sent} href="/outreach?status=SENT" />
    </div>
  );
}
