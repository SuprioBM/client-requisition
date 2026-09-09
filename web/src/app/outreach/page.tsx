"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { PageHeader } from "@/components/shared/page-header";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { OutreachStatusBadge } from "@/components/shared/badges";
import { QueryBoundary, EmptyState } from "@/components/shared/states";
import { useOutreachList } from "@/lib/query/hooks";
import { relativeTime } from "@/lib/utils";

const TABS = [
  ["PENDING_APPROVAL", "Pending Approval"],
  ["APPROVED", "Approved"],
  ["SENT", "Sent"],
  ["NOT_CONFIGURED", "Not Configured"],
  ["REJECTED", "Rejected"],
  ["all", "All"],
] as const;

function OutreachInner() {
  const router = useRouter();
  const params = useSearchParams();
  const [tab, setTab] = useState<string>(params.get("status") ?? "PENDING_APPROVAL");
  const query = useOutreachList(tab === "all" ? { limit: 200 } : { status: tab, limit: 200 });

  return (
    <div className="space-y-4">
      <PageHeader
        title="Outreach"
        description="Review, edit and approve AI-generated messages. Nothing is sent without your explicit action."
      />

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="flex-wrap">
          {TABS.map(([v, label]) => (
            <TabsTrigger key={v} value={v}>
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <div className="rounded-lg border">
        <QueryBoundary
          query={query}
          isEmpty={(d) => d.items.length === 0}
          empty={
            <EmptyState
              title={
                tab === "PENDING_APPROVAL"
                  ? "No messages awaiting approval"
                  : "Nothing here"
              }
              description="Once prospects are evaluated, generated outreach appears here."
              className="border-0"
            />
          }
        >
          {(data) => (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Business</TableHead>
                  <TableHead>Opportunity</TableHead>
                  <TableHead>Channel</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((m) => (
                  <TableRow
                    key={m.id}
                    className="cursor-pointer"
                    onClick={() => router.push(`/outreach/${m.id}`)}
                  >
                    <TableCell className="font-medium">{m.business_name ?? "—"}</TableCell>
                    <TableCell className="max-w-[220px] truncate text-xs text-muted-foreground">
                      {(m.strategy as Record<string, string>)?.primary_solution ?? "—"}
                    </TableCell>
                    <TableCell className="text-xs">{m.channel}</TableCell>
                    <TableCell>
                      <OutreachStatusBadge status={m.status} />
                    </TableCell>
                    <TableCell className="text-[11px] text-muted-foreground">
                      {relativeTime(m.created_at)}
                    </TableCell>
                    <TableCell>
                      <Button size="sm" variant="ghost">
                        Review
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </QueryBoundary>
      </div>
    </div>
  );
}

export default function OutreachPage() {
  return (
    <Suspense fallback={null}>
      <OutreachInner />
    </Suspense>
  );
}
