"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BarChart3,
  Briefcase,
  FlaskConical,
  LayoutDashboard,
  ListChecks,
  Mail,
  Radar,
  Settings,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useStats } from "@/lib/query/hooks";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/discover", label: "Discover", icon: Radar },
  { href: "/prospects", label: "Prospects", icon: Users },
  { href: "/research", label: "Research", icon: FlaskConical },
  { href: "/evaluation", label: "Evaluation", icon: BarChart3 },
  { href: "/outreach", label: "Outreach", icon: Mail, badge: "outreach" as const },
  { href: "/jobs", label: "Jobs", icon: ListChecks, badge: "jobs" as const },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { data: stats } = useStats();

  const badgeFor = (key?: "outreach" | "jobs") => {
    if (key === "outreach") return stats?.outreach.awaiting_approval || 0;
    if (key === "jobs") return stats?.jobs.active || 0;
    return 0;
  };

  return (
    <div className="flex h-full w-56 shrink-0 flex-col border-r bg-card">
      <div className="flex h-14 items-center gap-2 border-b px-4">
        <Briefcase className="h-5 w-5 text-info" />
        <div className="leading-tight">
          <p className="text-sm font-semibold">Requisition Agent</p>
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">operations</p>
        </div>
      </div>
      <nav className="flex-1 space-y-0.5 p-2">
        {NAV.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          const count = badgeFor(item.badge);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors",
                active
                  ? "bg-secondary font-medium text-foreground"
                  : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground",
              )}
            >
              <item.icon className="h-4 w-4" />
              <span className="flex-1">{item.label}</span>
              {count > 0 && (
                <span className="rounded-full bg-info/15 px-1.5 text-[10px] font-semibold text-info">
                  {count}
                </span>
              )}
            </Link>
          );
        })}
      </nav>
      <div className="flex items-center gap-2 border-t p-3 text-[10px] text-muted-foreground">
        <Activity className="h-3 w-3" />
        <span>Client Requisition Agent · V1</span>
      </div>
    </div>
  );
}
