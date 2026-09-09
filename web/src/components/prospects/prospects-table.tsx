"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  type ColumnDef,
  type VisibilityState,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { ArrowUpDown, ExternalLink, Settings2 } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ProspectStatusBadge, ScoreBadge } from "@/components/shared/badges";
import { QueryBoundary, EmptyState } from "@/components/shared/states";
import { Skeleton } from "@/components/ui/misc";
import { useBulkEvaluate, useBulkResearch, useProspects } from "@/lib/query/hooks";
import { relativeTime, safeExternalUrl } from "@/lib/utils";
import type { Prospect } from "@/lib/api/types";

type Props = {
  filters: Parameters<typeof useProspects>[0];
  compact?: boolean;
  onPageChange?: (offset: number) => void;
  onSortChange?: (sort: string) => void;
};

const STATUS_STEP = (p: Prospect, kind: "research" | "evaluation") => {
  if (kind === "research") {
    if (p.last_researched_at) return "complete";
    if (p.status === "RESEARCHING") return "running";
    return "pending";
  }
  if (p.last_evaluated_at) return "complete";
  if (p.status === "EVALUATING") return "running";
  if (p.status === "RESEARCHED" || p.last_researched_at) return "pending";
  return "—";
};

function StepBadge({ step }: { step: string }) {
  const v =
    step === "complete"
      ? "success"
      : step === "running"
        ? "running"
        : step === "pending"
          ? "neutral"
          : "neutral";
  return step === "—" ? (
    <span className="text-xs text-muted-foreground">—</span>
  ) : (
    <Badge variant={v}>{step}</Badge>
  );
}

export function ProspectsTable({ filters, compact, onPageChange, onSortChange }: Props) {
  const router = useRouter();
  const query = useProspects(filters);
  const [rowSelection, setRowSelection] = useState<Record<string, boolean>>({});
  const [colVis, setColVis] = useState<VisibilityState>(
    compact ? { location: false, website: false, phone: false, reviews: false, source: false } : {},
  );
  const bulkResearch = useBulkResearch();
  const bulkEvaluate = useBulkEvaluate();

  const columns = useMemo<ColumnDef<Prospect>[]>(
    () => [
      {
        id: "select",
        header: ({ table }) => (
          <Checkbox
            checked={
              table.getIsAllRowsSelected()
                ? true
                : table.getIsSomeRowsSelected()
                  ? "indeterminate"
                  : false
            }
            onCheckedChange={(v) => table.toggleAllRowsSelected(!!v)}
            aria-label="Select all"
          />
        ),
        cell: ({ row }) => (
          <Checkbox
            checked={row.getIsSelected()}
            onCheckedChange={(v) => row.toggleSelected(!!v)}
            onClick={(e) => e.stopPropagation()}
            aria-label="Select row"
          />
        ),
        enableHiding: false,
      },
      {
        accessorKey: "business_name",
        header: "Business",
        cell: ({ row }) => (
          <div className="min-w-0">
            <p className="truncate font-medium">{row.original.business_name}</p>
            <p className="truncate text-[11px] text-muted-foreground">
              {row.original.industry ?? "—"}
              {row.original.quality_status === "REVIEW" && (
                <span className="ml-1 text-warning">· review</span>
              )}
            </p>
          </div>
        ),
      },
      {
        id: "location",
        header: "Location",
        cell: ({ row }) => (
          <span className="text-xs text-muted-foreground">
            {[row.original.city, row.original.country].filter(Boolean).join(", ") || "—"}
          </span>
        ),
      },
      {
        id: "website",
        header: "Website",
        cell: ({ row }) => {
          const url = safeExternalUrl(row.original.website);
          return url ? (
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="flex items-center gap-1 text-xs text-info hover:underline"
            >
              {row.original.canonical_domain}
              <ExternalLink className="h-3 w-3" />
            </a>
          ) : (
            <span className="text-xs text-muted-foreground">—</span>
          );
        },
      },
      {
        id: "phone",
        header: "Phone",
        cell: ({ row }) => (
          <span className="font-mono text-xs">{row.original.phone ?? "—"}</span>
        ),
      },
      {
        accessorKey: "rating",
        header: "Rating",
        cell: ({ row }) => (
          <span className="text-xs">
            {row.original.rating != null ? `${row.original.rating}★` : "—"}
          </span>
        ),
      },
      {
        id: "reviews",
        header: "Reviews",
        cell: ({ row }) => (
          <span className="text-xs text-muted-foreground">{row.original.review_count ?? "—"}</span>
        ),
      },
      {
        id: "research",
        header: "Research",
        cell: ({ row }) => <StepBadge step={STATUS_STEP(row.original, "research")} />,
      },
      {
        id: "evaluation",
        header: "Evaluation",
        cell: ({ row }) => <StepBadge step={STATUS_STEP(row.original, "evaluation")} />,
      },
      {
        id: "score",
        header: () => (
          <button
            className="flex items-center gap-1"
            onClick={() => onSortChange?.("score")}
          >
            Score <ArrowUpDown className="h-3 w-3" />
          </button>
        ),
        cell: ({ row }) => <ScoreBadge score={row.original.evaluation?.score_total} />,
      },
      {
        id: "status",
        header: "Status",
        cell: ({ row }) => <ProspectStatusBadge status={row.original.status} />,
      },
      {
        id: "updated",
        header: "Updated",
        cell: ({ row }) => (
          <span className="text-[11px] text-muted-foreground">
            {relativeTime(row.original.updated_at)}
          </span>
        ),
      },
    ],
    [onSortChange],
  );

  const table = useReactTable({
    data: query.data?.items ?? [],
    columns,
    state: { rowSelection, columnVisibility: colVis },
    onRowSelectionChange: setRowSelection,
    onColumnVisibilityChange: setColVis,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (r) => r.id,
    manualPagination: true,
  });

  const selectedIds = Object.keys(rowSelection).filter((k) => rowSelection[k]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {selectedIds.length > 0 ? (
            <>
              <span className="text-xs text-muted-foreground">{selectedIds.length} selected</span>
              <Button
                size="sm"
                variant="outline"
                disabled={bulkResearch.isPending}
                onClick={() => bulkResearch.mutate(selectedIds, { onSuccess: () => setRowSelection({}) })}
              >
                Research selected
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={bulkEvaluate.isPending}
                onClick={() => bulkEvaluate.mutate(selectedIds, { onSuccess: () => setRowSelection({}) })}
              >
                Evaluate selected
              </Button>
            </>
          ) : (
            <span className="text-xs text-muted-foreground">
              {query.data ? `${query.data.total} prospects` : ""}
            </span>
          )}
        </div>
        {!compact && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="sm" variant="outline">
                <Settings2 className="h-3.5 w-3.5" /> Columns
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Toggle columns</DropdownMenuLabel>
              {table
                .getAllColumns()
                .filter((c) => c.getCanHide())
                .map((c) => (
                  <DropdownMenuCheckboxItem
                    key={c.id}
                    checked={c.getIsVisible()}
                    onCheckedChange={(v) => c.toggleVisibility(!!v)}
                    className="capitalize"
                  >
                    {c.id}
                  </DropdownMenuCheckboxItem>
                ))}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>

      <div className="rounded-lg border">
        <QueryBoundary
          query={query}
          skeleton={
            <div className="space-y-2 p-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-9 w-full" />
              ))}
            </div>
          }
          isEmpty={(d) => d.items.length === 0}
          empty={
            <EmptyState
              title="No prospects yet"
              description="Start your first discovery job to find potential clients."
              className="border-0"
            />
          }
        >
          {() => (
            <Table>
              <TableHeader>
                {table.getHeaderGroups().map((hg) => (
                  <TableRow key={hg.id}>
                    {hg.headers.map((h) => (
                      <TableHead key={h.id}>
                        {h.isPlaceholder
                          ? null
                          : flexRender(h.column.columnDef.header, h.getContext())}
                      </TableHead>
                    ))}
                  </TableRow>
                ))}
              </TableHeader>
              <TableBody>
                {table.getRowModel().rows.map((row) => (
                  <TableRow
                    key={row.id}
                    className="cursor-pointer animate-fade-in"
                    onClick={() => router.push(`/prospects/${row.original.id}`)}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <TableCell key={cell.id}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </QueryBoundary>
      </div>

      {!compact && query.data && query.data.total > (filters?.limit ?? 50) && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            {(filters?.offset ?? 0) + 1}–
            {Math.min((filters?.offset ?? 0) + (filters?.limit ?? 50), query.data.total)} of{" "}
            {query.data.total}
          </span>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={(filters?.offset ?? 0) === 0}
              onClick={() => onPageChange?.(Math.max(0, (filters?.offset ?? 0) - (filters?.limit ?? 50)))}
            >
              Previous
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={(filters?.offset ?? 0) + (filters?.limit ?? 50) >= query.data.total}
              onClick={() => onPageChange?.((filters?.offset ?? 0) + (filters?.limit ?? 50))}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
