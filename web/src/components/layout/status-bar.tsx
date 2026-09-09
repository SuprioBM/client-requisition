"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useHealth, useActiveJobs } from "@/lib/query/hooks";

const DOT: Record<string, string> = {
  online: "bg-success",
  degraded: "bg-warning",
  offline: "bg-destructive",
  unknown: "bg-muted-foreground",
};

export function StatusBar({ onMenu }: { onMenu?: () => void }) {
  const { data: health } = useHealth();
  const { data: active } = useActiveJobs();
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const components = health?.components ?? {};
  const running = (active?.items ?? []).some((j) => j.status === "RUNNING");

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b bg-card px-4">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenu}
          className="rounded-md p-1.5 text-muted-foreground hover:bg-secondary md:hidden"
          aria-label="Open navigation"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        <div className="flex items-center gap-1.5">
          <span
            className={cn(
              "inline-block h-2 w-2 rounded-full",
              running ? "animate-pulse-subtle bg-running" : "bg-success",
            )}
          />
          <span className="text-sm font-semibold">
            {running ? "RUNNING" : "IDLE"}
          </span>
        </div>
      </div>

      <div className="hidden items-center gap-4 text-xs text-muted-foreground sm:flex">
        {["api", "worker", "redis", "database"].map((c) => (
          <div key={c} className="flex items-center gap-1.5">
            <span className={cn("h-2 w-2 rounded-full", DOT[components[c] ?? "unknown"])} />
            <span className="capitalize">{c}</span>
          </div>
        ))}
        {health?.env && (
          <span className="rounded bg-secondary px-1.5 py-0.5 font-mono uppercase">
            {health.env}
          </span>
        )}
      </div>

      <Button
        variant="ghost"
        size="icon"
        onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        aria-label="Toggle theme"
      >
        {mounted && theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </Button>
    </header>
  );
}
