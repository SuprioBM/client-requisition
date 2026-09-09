"use client";

import { use } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { QueryBoundary } from "@/components/shared/states";
import { OutreachReview } from "@/components/outreach/outreach-review";
import { useOutreachItem } from "@/lib/query/hooks";

export default function OutreachReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const query = useOutreachItem(id);

  return (
    <div className="space-y-4">
      <Link
        href="/outreach"
        className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-3 w-3" /> All outreach
      </Link>
      <QueryBoundary query={query}>
        {(message) => (
          <>
            <PageHeader
              title={`${message.business_name ?? "Outreach"} · ${message.channel}`}
              description={
                <Link
                  href={`/prospects/${message.prospect_id}`}
                  className="text-xs text-info hover:underline"
                >
                  View prospect intelligence →
                </Link>
              }
            />
            <OutreachReview message={message} />
          </>
        )}
      </QueryBoundary>
    </div>
  );
}
