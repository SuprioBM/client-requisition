export const qk = {
  health: ["health"] as const,
  stats: ["stats"] as const,
  activity: (limit: number) => ["activity", limit] as const,
  providerAnalytics: ["analytics", "providers"] as const,
  researchAnalytics: ["analytics", "research"] as const,
  settings: ["settings"] as const,

  jobs: (filters: Record<string, unknown>) => ["jobs", filters] as const,
  job: (id: string) => ["job", id] as const,

  prospects: (filters: Record<string, unknown>) => ["prospects", filters] as const,
  prospect: (id: string) => ["prospect", id] as const,
  profile: (id: string) => ["profile", id] as const,

  research: (id: string) => ["research", id] as const,
  evaluation: (id: string) => ["evaluation", id] as const,
  evaluationHistory: (id: string) => ["evaluation-history", id] as const,

  outreach: (filters: Record<string, unknown>) => ["outreach", filters] as const,
  outreachItem: (id: string) => ["outreach-item", id] as const,
  prospectOutreach: (id: string) => ["prospect-outreach", id] as const,
};
