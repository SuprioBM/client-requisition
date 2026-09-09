"use client";

import { Badge } from "@/components/ui/badge";
import { DetectionIndicator } from "@/components/shared/badges";
import { KeyValue } from "@/components/shared/section";
import { EmptyState } from "@/components/shared/states";
import { orNotAvailable, relativeTime, safeExternalUrl } from "@/lib/utils";
import type { ProfileResponse } from "@/lib/api/types";

const WEBSITE_STATUS_VARIANT: Record<string, Parameters<typeof Badge>[0]["variant"]> = {
  ACTIVE: "success",
  REDIRECTED: "info",
  NOT_FOUND: "error",
  TIMEOUT: "warning",
  FORBIDDEN: "warning",
  SERVER_ERROR: "error",
  INVALID: "error",
  UNKNOWN: "neutral",
};

export function ResearchPanel({
  research,
  lastResearched,
}: {
  research: ProfileResponse["research"];
  lastResearched: string | null;
}) {
  if (!research) {
    return (
      <EmptyState
        title="Not researched yet"
        description="Run research to fetch and analyze the website, collect social presence, and gather evidence."
      />
    );
  }

  const ws = (research.signals?.website ?? {}) as Record<string, unknown>;

  const bool = (k: string): boolean | null =>
    ws[k] === true ? true : ws[k] === false ? false : null;

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <div className="space-y-3">
        <KeyValue
          rows={[
            [
              "Website status",
              <Badge
                key="s"
                variant={WEBSITE_STATUS_VARIANT[research.website_status ?? "UNKNOWN"] ?? "neutral"}
              >
                {research.website_status ?? "unknown"}
              </Badge>,
            ],
            ["Pages analyzed", orNotAvailable(ws.pages_analyzed)],
            ["Content length", ws.total_text_length ? `${ws.total_text_length} chars` : "Not available"],
            ["Sources used", (research.signals && "") || ""],
            ["Last researched", relativeTime(lastResearched)],
            [
              "Final URL",
              safeExternalUrl(research.signals?.website?.final_url as string) ? (
                <a
                  className="text-info hover:underline"
                  href={safeExternalUrl(research.signals?.website?.final_url as string)!}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {String(research.signals?.website?.final_url)}
                </a>
              ) : (
                "Not available"
              ),
            ],
          ]}
        />
        {Object.keys(research.social_profiles ?? {}).length > 0 ? (
          <div>
            <p className="mb-1 text-[11px] uppercase text-muted-foreground">Social presence</p>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(research.social_profiles).map(([platform, url]) => (
                <a
                  key={platform}
                  href={safeExternalUrl(url) ?? "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-full border border-info/30 bg-info/10 px-2 py-0.5 text-xs text-info hover:underline"
                >
                  {platform}
                </a>
              ))}
            </div>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">No social profiles linked from researched pages.</p>
        )}
      </div>

      <div className="rounded-lg border p-3">
        <p className="mb-2 text-[11px] font-medium uppercase text-muted-foreground">
          Website analysis
        </p>
        <div className="divide-y">
          <DetectionIndicator state={bool("is_https")} label="HTTPS" />
          <DetectionIndicator state={ws.status === "ACTIVE" ? true : ws.status ? false : null} label="Website reachable" />
          <DetectionIndicator state={bool("has_meta_description")} label="Meta description" />
          <DetectionIndicator state={bool("has_viewport_meta")} label="Mobile viewport tag" />
          <DetectionIndicator state={bool("has_primary_cta")} label="Primary call-to-action" />
          <DetectionIndicator state={bool("has_booking_mechanism")} label="Online booking" />
          <DetectionIndicator state={bool("has_online_ordering")} label="Online ordering" />
          <DetectionIndicator state={bool("has_contact_form")} label="Contact form" />
          <DetectionIndicator state={bool("has_faq_section")} label="FAQ section" />
          <DetectionIndicator state={bool("has_live_chat")} label="Live chat widget" />
        </div>
        {Array.isArray(ws.technology_signals) && ws.technology_signals.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {(ws.technology_signals as string[]).map((t) => (
              <span key={t} className="rounded bg-secondary px-1.5 py-0.5 font-mono text-[10px]">
                {t}
              </span>
            ))}
          </div>
        )}
        <p className="mt-2 text-[10px] text-muted-foreground">
          “Not detected” means no such element was found on the researched pages — not a
          confirmed absence.
        </p>
      </div>
    </div>
  );
}
