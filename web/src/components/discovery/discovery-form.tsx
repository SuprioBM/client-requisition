"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { z } from "zod";
import { Radar } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useStartDiscovery } from "@/lib/query/hooks";
import { ApiError } from "@/lib/api/client";
import { previewPlan } from "@/lib/api/endpoints";

const schema = z.object({
  country: z.string().trim().min(2, "Country is required"),
  city: z.string().trim().min(1, "City is required"),
  industry: z.string().trim().min(2, "Industry is required"),
  radius_km: z.coerce.number().gt(0).max(50),
  target_leads: z.coerce.number().int().min(1).max(500),
});

export function DiscoveryForm() {
  const router = useRouter();
  const start = useStartDiscovery();
  const [values, setValues] = useState({
    country: "Bangladesh",
    city: "Dhaka",
    industry: "dental",
    radius_km: "10",
    target_leads: "20",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [plan, setPlan] = useState<string[] | null>(null);
  const [submitted, setSubmitted] = useState<string | null>(null);

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setValues((v) => ({ ...v, [k]: e.target.value }));

  async function onPreview() {
    setPlan(null);
    try {
      const p = await previewPlan({
        country: values.country,
        city: values.city,
        industry: values.industry,
      });
      setPlan(p.queries);
    } catch {
      setPlan([]);
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const parsed = schema.safeParse(values);
    if (!parsed.success) {
      const errs: Record<string, string> = {};
      for (const issue of parsed.error.issues) errs[String(issue.path[0])] = issue.message;
      setErrors(errs);
      return;
    }
    setErrors({});
    start.mutate(parsed.data, {
      onSuccess: (res) => {
        setSubmitted(res.job_id);
        setTimeout(() => router.push(`/jobs/${res.job_id}`), 700);
      },
      onError: (err) => {
        if (err instanceof ApiError && err.context?.errors) {
          const errs: Record<string, string> = {};
          for (const d of err.context.errors as { loc: string[]; msg: string }[]) {
            errs[d.loc[d.loc.length - 1]] = d.msg;
          }
          setErrors(errs);
        }
      },
    });
  }

  const buttonLabel = submitted
    ? "Discovery started"
    : start.isPending
      ? "Starting…"
      : "Start Discovery";

  return (
    <div className="grid gap-6 lg:grid-cols-[400px_1fr]">
      <Card>
        <CardHeader>
          <CardTitle>New Discovery Job</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4" noValidate>
            <Field label="Country" error={errors.country}>
              <Input value={values.country} onChange={set("country")} />
            </Field>
            <Field label="City" error={errors.city}>
              <Input value={values.city} onChange={set("city")} />
            </Field>
            <Field label="Industry" error={errors.industry}>
              <Input value={values.industry} onChange={set("industry")} placeholder="e.g. dental clinics" />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Radius (km)" error={errors.radius_km}>
                <Input type="number" value={values.radius_km} onChange={set("radius_km")} />
              </Field>
              <Field label="Target leads" error={errors.target_leads}>
                <Input type="number" value={values.target_leads} onChange={set("target_leads")} />
              </Field>
            </div>

            <div className="flex gap-2 pt-1">
              <Button type="submit" disabled={start.isPending || !!submitted} className="flex-1">
                <Radar className="h-4 w-4" />
                {buttonLabel}
              </Button>
              <Button type="button" variant="outline" onClick={onPreview}>
                Preview plan
              </Button>
            </div>

            {submitted && (
              <p className="rounded-md bg-success/10 px-3 py-2 text-xs text-success">
                Job created: <span className="font-mono">{submitted}</span> — opening monitor…
              </p>
            )}
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Query Plan Preview</CardTitle>
        </CardHeader>
        <CardContent>
          {plan === null ? (
            <p className="text-sm text-muted-foreground">
              The planner expands your industry term into a small set of diverse search
              queries (deterministic, no LLM). Click “Preview plan” to see them.
            </p>
          ) : plan.length === 0 ? (
            <p className="text-sm text-muted-foreground">No plan available.</p>
          ) : (
            <ul className="space-y-1.5">
              {plan.map((q) => (
                <li key={q} className="rounded-md border px-3 py-1.5 text-sm font-mono">
                  {q}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <Label>{label}</Label>
      {children}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
