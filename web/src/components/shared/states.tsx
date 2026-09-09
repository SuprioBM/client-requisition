"use client";

import type { UseQueryResult } from "@tanstack/react-query";
import { AlertTriangle, Inbox, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/misc";
import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils";

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  className,
}: {
  icon?: React.ComponentType<{ className?: string }>;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed py-12 text-center",
        className,
      )}
    >
      <Icon className="h-8 w-8 text-muted-foreground" />
      <div className="space-y-1">
        <p className="text-sm font-medium">{title}</p>
        {description && (
          <p className="max-w-sm text-xs text-muted-foreground">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}

export function ErrorPanel({
  error,
  onRetry,
  compact,
}: {
  error: unknown;
  onRetry?: () => void;
  compact?: boolean;
}) {
  const code = error instanceof ApiError ? error.code : "ERROR";
  const message = error instanceof Error ? error.message : String(error);
  const isBackendDown =
    error instanceof ApiError && ["BACKEND_UNREACHABLE", "NETWORK_ERROR"].includes(error.code);

  return (
    <div
      className={cn(
        "rounded-lg border border-destructive/30 bg-destructive/5 text-sm",
        compact ? "p-3" : "p-4",
      )}
    >
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
        <div className="space-y-1">
          <p className="font-medium text-destructive">
            {isBackendDown ? "Backend unavailable" : "Unable to load data"}
          </p>
          <p className="text-xs text-muted-foreground">
            <span className="font-mono">{code}</span> — {message}
          </p>
          {onRetry && (
            <Button size="sm" variant="outline" className="mt-2" onClick={onRetry}>
              <RefreshCw className="h-3.5 w-3.5" />
              Retry
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Renders one of loading / error / empty / content for a query. Keeps every
 * page consistent and prevents blank screens or silently-swallowed errors.
 */
export function QueryBoundary<T>({
  query,
  children,
  skeleton,
  empty,
  isEmpty,
}: {
  query: UseQueryResult<T>;
  children: (data: T) => React.ReactNode;
  skeleton?: React.ReactNode;
  empty?: React.ReactNode;
  isEmpty?: (data: T) => boolean;
}) {
  if (query.isPending) {
    return <>{skeleton ?? <DefaultSkeleton />}</>;
  }
  if (query.isError) {
    return <ErrorPanel error={query.error} onRetry={() => query.refetch()} />;
  }
  const data = query.data as T;
  if (empty && isEmpty?.(data)) {
    return <>{empty}</>;
  }
  return <>{children(data)}</>;
}

function DefaultSkeleton() {
  return (
    <div className="space-y-2">
      <Skeleton className="h-8 w-full" />
      <Skeleton className="h-8 w-11/12" />
      <Skeleton className="h-8 w-10/12" />
    </div>
  );
}
