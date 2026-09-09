"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Search } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ProspectsTable } from "@/components/prospects/prospects-table";

const STATUS_FILTERS = [
  ["all", "All"],
  ["DISCOVERED", "New"],
  ["RESEARCHED", "Researched"],
  ["EVALUATING", "Evaluating"],
  ["EVALUATED", "Evaluated"],
  ["OUTREACH_DRAFTED", "Outreach ready"],
  ["CONTACTED", "Contacted"],
  ["REJECTED", "Rejected"],
] as const;

function ProspectsInner() {
  const params = useSearchParams();
  const [status, setStatus] = useState<string>(params.get("status") ?? "all");
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [minScore, setMinScore] = useState<number | undefined>(undefined);
  const [sort, setSort] = useState("created_at");
  const [offset, setOffset] = useState(0);

  // debounce search
  function onSearch(v: string) {
    setSearch(v);
    setOffset(0);
    window.clearTimeout((onSearch as unknown as { t?: number }).t);
    (onSearch as unknown as { t?: number }).t = window.setTimeout(() => setDebounced(v), 350);
  }

  const filters = {
    status: status === "all" ? undefined : status,
    q: debounced || undefined,
    min_score: minScore,
    sort,
    limit: 50,
    offset,
  };

  return (
    <div className="space-y-4">
      <PageHeader title="Prospects" description="Discovered businesses and their pipeline state." />

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-64">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => onSearch(e.target.value)}
            placeholder="Search name, domain, phone, city…"
            className="pl-8"
          />
        </div>
        <div className="flex flex-wrap gap-1.5">
          {STATUS_FILTERS.map(([v, label]) => (
            <Button
              key={v}
              size="sm"
              variant={status === v ? "default" : "outline"}
              onClick={() => {
                setStatus(v);
                setOffset(0);
              }}
            >
              {label}
            </Button>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          {[0, 50, 70, 85].map((s) => (
            <Button
              key={s}
              size="sm"
              variant={minScore === (s || undefined) ? "default" : "outline"}
              onClick={() => {
                setMinScore(s || undefined);
                setOffset(0);
              }}
            >
              {s === 0 ? "Any score" : `≥${s}`}
            </Button>
          ))}
        </div>
      </div>

      <ProspectsTable
        filters={filters}
        onPageChange={setOffset}
        onSortChange={(s) => setSort((cur) => (cur === s ? "created_at" : s))}
      />
    </div>
  );
}

export default function ProspectsPage() {
  return (
    <Suspense fallback={null}>
      <ProspectsInner />
    </Suspense>
  );
}
