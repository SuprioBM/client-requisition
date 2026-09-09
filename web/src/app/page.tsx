"use client";

import Link from "next/link";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { KpiGrid } from "@/components/dashboard/kpi-grid";
import { SystemStatus } from "@/components/dashboard/system-status";
import { ActiveJobs } from "@/components/dashboard/active-jobs";
import { ActivityFeed } from "@/components/shared/activity-feed";
import { ProspectsTable } from "@/components/prospects/prospects-table";
import { Radar } from "lucide-react";

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="Operational overview of the client discovery pipeline."
        action={
          <Button asChild>
            <Link href="/discover">
              <Radar className="h-4 w-4" /> New discovery
            </Link>
          </Button>
        }
      />

      <KpiGrid />

      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="space-y-6">
          <ActiveJobs />
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Live Prospect Stream</CardTitle>
              <Link href="/prospects" className="text-xs text-info hover:underline">
                View all →
              </Link>
            </CardHeader>
            <CardContent>
              <ProspectsTable filters={{ limit: 12, sort: "created_at" }} compact />
            </CardContent>
          </Card>
        </div>
        <div className="space-y-6">
          <SystemStatus />
          <ActivityFeed />
        </div>
      </div>
    </div>
  );
}
