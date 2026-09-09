"use client";

import { Check, CheckCheck } from "lucide-react";

/** Renders untrusted AI text as plain text only. */
export function EmailPreview({ subject, body }: { subject: string | null; body: string }) {
  return (
    <div className="overflow-hidden rounded-lg border bg-background">
      <div className="border-b bg-muted/40 px-4 py-2">
        <p className="text-[11px] uppercase text-muted-foreground">Subject</p>
        <p className="text-sm font-medium">{subject || "(no subject)"}</p>
      </div>
      <div className="whitespace-pre-wrap px-4 py-3 text-sm leading-relaxed">{body}</div>
    </div>
  );
}

export function WhatsAppPreview({ body }: { body: string }) {
  return (
    <div className="rounded-lg bg-[#0b141a] p-4">
      <div className="ml-auto max-w-[85%] rounded-lg rounded-tr-none bg-[#005c4b] px-3 py-2 text-sm text-white shadow">
        <p className="whitespace-pre-wrap leading-relaxed">{body}</p>
        <div className="mt-1 flex items-center justify-end gap-1 text-[10px] text-white/60">
          <span>now</span>
          <CheckCheck className="h-3 w-3" />
        </div>
      </div>
    </div>
  );
}

export function Delivered() {
  return <Check className="h-3 w-3" />;
}
