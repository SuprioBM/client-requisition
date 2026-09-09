"use client";

import { use } from "react";
import Link from "next/link";
import { ArrowLeft, BarChart3, ExternalLink, FlaskConical } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Section, KeyValue } from "@/components/shared/section";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { QueryBoundary } from "@/components/shared/states";
import { ProspectStatusBadge } from "@/components/shared/badges";
import { DiscoverySources } from "@/components/prospect/discovery-sources";
import { ResearchPanel } from "@/components/prospect/research-panel";
import { EvidenceList } from "@/components/prospect/evidence-list";
import { PainPoints } from "@/components/prospect/pain-points";
import { Solutions } from "@/components/prospect/solutions";
import { OpportunityScore } from "@/components/prospect/opportunity-score";
import { OutreachSection } from "@/components/prospect/outreach-section";
import { useProfile, useProspect, useStartEvaluation, useStartResearch } from "@/lib/query/hooks";
import { orNotAvailable, safeExternalUrl } from "@/lib/utils";

export default function ProspectDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const profileQuery = useProfile(id);
  const prospectQuery = useProspect(id);
  const research = useStartResearch(id);
  const evaluate = useStartEvaluation(id);

  return (
    <div className="space-y-5">
      <Link
        href="/prospects"
        className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-3 w-3" /> All prospects
      </Link>

      <QueryBoundary query={profileQuery}>
        {(profile) => {
          const b = profile.business;
          const site = safeExternalUrl(b.website);
          const evidence = profile.research?.evidence ?? [];
          const painPointEvidenceIds =
            profile.evaluation?.pain_points.flatMap((p) => p.evidence_ids) ?? [];

          return (
            <>
              <PageHeader
                title={b.name}
                description={
                  <span className="flex flex-wrap items-center gap-2">
                    <ProspectStatusBadge status={b.status as never} />
                    <span className="text-xs text-muted-foreground">
                      {[b.industry, b.location.city, b.location.country].filter(Boolean).join(" · ")}
                    </span>
                  </span>
                }
                action={
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => research.mutate(true)}
                      disabled={research.isPending}
                    >
                      <FlaskConical className="h-3.5 w-3.5" />
                      {profile.research ? "Re-research" : "Research now"}
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => evaluate.mutate()}
                      disabled={evaluate.isPending}
                    >
                      <BarChart3 className="h-3.5 w-3.5" />
                      {profile.evaluation ? "Re-evaluate" : "Evaluate"}
                    </Button>
                  </div>
                }
              />

              <div className="grid gap-5 xl:grid-cols-[1fr_320px]">
                <div className="space-y-6">
                  <Section title="Research & Website">
                    <Card>
                      <CardContent className="pt-4">
                        <ResearchPanel
                          research={profile.research}
                          lastResearched={prospectQuery.data?.last_researched_at ?? null}
                        />
                      </CardContent>
                    </Card>
                  </Section>

                  <Section
                    title="Evidence"
                    description="Objective, sourced observations. Every AI claim below cites these."
                  >
                    <EvidenceList evidence={evidence} highlightIds={painPointEvidenceIds} />
                  </Section>

                  <Section title="Pain Points">
                    {profile.evaluation ? (
                      <PainPoints
                        painPoints={profile.evaluation.pain_points}
                        evidence={evidence}
                      />
                    ) : (
                      <Card>
                        <CardContent className="pt-4 text-sm text-muted-foreground">
                          Not evaluated yet.
                        </CardContent>
                      </Card>
                    )}
                  </Section>

                  <Section title="Recommended Solutions">
                    {profile.evaluation ? (
                      <Solutions solutions={profile.evaluation.solutions} />
                    ) : (
                      <Card>
                        <CardContent className="pt-4 text-sm text-muted-foreground">
                          Not evaluated yet.
                        </CardContent>
                      </Card>
                    )}
                  </Section>

                  {profile.evaluation && (
                    <Section title="Opportunity & Score">
                      <Card>
                        <CardContent className="space-y-4 pt-4">
                          <OpportunityScore evaluation={profile.evaluation} />
                          {profile.evaluation.opportunity_summary && (
                            <p className="text-sm">{profile.evaluation.opportunity_summary}</p>
                          )}
                          {profile.evaluation.opportunity_reasoning && (
                            <details className="text-sm">
                              <summary className="cursor-pointer text-xs font-medium uppercase text-muted-foreground">
                                Reasoning
                              </summary>
                              <p className="mt-1 whitespace-pre-wrap text-muted-foreground">
                                {profile.evaluation.opportunity_reasoning}
                              </p>
                            </details>
                          )}
                          <p className="text-[11px] text-muted-foreground">
                            model {orNotAvailable(profile.evaluation.model)} · prompt{" "}
                            {profile.evaluation.prompt_version} · scoring{" "}
                            {profile.evaluation.scoring_version}
                          </p>
                        </CardContent>
                      </Card>
                    </Section>
                  )}

                  <Section title="Outreach">
                    <OutreachSection
                      prospectId={id}
                      canGenerate={!!profile.evaluation?.is_opportunity}
                    />
                  </Section>
                </div>

                <div className="space-y-5">
                  <Card>
                    <CardHeader>
                      <CardTitle>Business</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <KeyValue
                        rows={[
                          ["Industry", orNotAvailable(b.industry)],
                          [
                            "Location",
                            orNotAvailable(
                              [b.location.city, b.location.country].filter(Boolean).join(", ") ||
                                null,
                            ),
                          ],
                          ["Address", orNotAvailable(b.location.address)],
                          [
                            "Website",
                            site ? (
                              <a
                                href={site}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 text-info hover:underline"
                              >
                                {b.website} <ExternalLink className="h-3 w-3" />
                              </a>
                            ) : (
                              "Not available"
                            ),
                          ],
                          ["Phone", orNotAvailable(b.contact.phone)],
                          ["Email", orNotAvailable(b.contact.email)],
                          [
                            "Rating",
                            b.rating != null
                              ? `${b.rating} (${b.review_count ?? 0} reviews)`
                              : "Not available",
                          ],
                          ["Quality", b.quality_status],
                        ]}
                      />
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>Discovery Sources</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <DiscoverySources sources={profile.discovery.sources} />
                    </CardContent>
                  </Card>
                </div>
              </div>
            </>
          );
        }}
      </QueryBoundary>
    </div>
  );
}
