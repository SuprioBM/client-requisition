"use client";

import { useEffect, useState } from "react";
import { Check, Pencil, Send, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { OutreachStatusBadge } from "@/components/shared/badges";
import { EmailPreview, WhatsAppPreview } from "./previews";
import {
  useApproveOutreach,
  useRejectOutreach,
  useSaveOutreach,
  useSendOutreach,
} from "@/lib/query/hooks";
import { orNotAvailable } from "@/lib/utils";
import type { OutreachMessage } from "@/lib/api/types";

export function OutreachReview({ message }: { message: OutreachMessage }) {
  const isEmail = message.channel === "EMAIL";
  const [subject, setSubject] = useState(message.subject ?? "");
  const [body, setBody] = useState(message.body);
  const [editing, setEditing] = useState(false);
  const [confirm, setConfirm] = useState<null | "approve" | "reject">(null);

  useEffect(() => {
    setSubject(message.subject ?? "");
    setBody(message.body);
  }, [message.id, message.subject, message.body]);

  const save = useSaveOutreach(message.id);
  const approve = useApproveOutreach(message.id);
  const reject = useRejectOutreach(message.id);
  const send = useSendOutreach(message.id);

  const dirty = subject !== (message.subject ?? "") || body !== message.body;
  const canEdit = ["PENDING_APPROVAL", "DRAFTED"].includes(message.status);
  const strategy = message.strategy as Record<string, string>;

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
      <div className="space-y-4">
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>{message.channel} message</CardTitle>
            <div className="flex items-center gap-2">
              <OutreachStatusBadge status={message.status} />
              {canEdit && (
                <Button size="sm" variant="ghost" onClick={() => setEditing((v) => !v)}>
                  <Pencil className="h-3.5 w-3.5" /> {editing ? "Preview" : "Edit"}
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {editing ? (
              <>
                {isEmail && (
                  <div className="space-y-1">
                    <Label>Subject</Label>
                    <Input value={subject} onChange={(e) => setSubject(e.target.value)} />
                  </div>
                )}
                <div className="space-y-1">
                  <Label>Body</Label>
                  <Textarea
                    value={body}
                    onChange={(e) => setBody(e.target.value)}
                    rows={isEmail ? 12 : 6}
                  />
                  <p className="text-right text-[11px] text-muted-foreground">
                    {body.length} characters
                  </p>
                </div>
                <Button
                  size="sm"
                  disabled={!dirty || save.isPending}
                  onClick={() =>
                    save.mutate(
                      { subject: isEmail ? subject : undefined, body },
                      { onSuccess: () => setEditing(false) },
                    )
                  }
                >
                  {save.isPending ? "Saving…" : "Save changes"}
                </Button>
              </>
            ) : isEmail ? (
              <EmailPreview subject={subject} body={body} />
            ) : (
              <WhatsAppPreview body={body} />
            )}
          </CardContent>
        </Card>

        {message.status === "PENDING_APPROVAL" && (
          <div className="flex gap-2">
            <Button className="flex-1" variant="success" onClick={() => setConfirm("approve")}>
              <Check className="h-4 w-4" /> Approve
            </Button>
            <Button className="flex-1" variant="destructive" onClick={() => setConfirm("reject")}>
              <X className="h-4 w-4" /> Reject
            </Button>
          </div>
        )}
        {message.status === "APPROVED" && (
          <Button className="w-full" onClick={() => send.mutate(false)} disabled={send.isPending}>
            <Send className="h-4 w-4" /> {send.isPending ? "Sending…" : "Send message"}
          </Button>
        )}
        {message.status === "NOT_CONFIGURED" && (
          <p className="rounded-md bg-muted p-3 text-xs text-muted-foreground">
            Approved, but no sending provider is configured for this channel — the message was not
            sent. Configure SMTP (email) on the backend to enable real sending.
          </p>
        )}
      </div>

      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Outreach Strategy</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-2 text-sm">
              {[
                ["Observation", strategy.primary_observation],
                ["Problem", strategy.primary_problem],
                ["Solution", strategy.primary_solution],
                ["Value", strategy.value_proposition],
                ["Tone", strategy.tone],
                ["CTA", strategy.call_to_action],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt className="text-[11px] uppercase text-muted-foreground">{k}</dt>
                  <dd>{orNotAvailable(v)}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Delivery</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-1.5 text-sm">
              <Row k="To" v={orNotAvailable(message.to_address)} />
              <Row k="Evidence cited" v={String(message.evidence_ids.length)} />
              <Row k="Follow-ups" v={String(message.follow_up_count)} />
              <Row k="Sent at" v={orNotAvailable(message.sent_at)} />
            </dl>
            {message.events.length > 0 && (
              <ul className="mt-3 space-y-1 border-t pt-2 text-[11px] text-muted-foreground">
                {message.events.map((e, i) => (
                  <li key={i} className="capitalize">
                    {e.type.replace(/_/g, " ")}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={confirm !== null} onOpenChange={(o) => !o && setConfirm(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {confirm === "approve" ? "Approve this message?" : "Reject this message?"}
            </DialogTitle>
            <DialogDescription>
              {confirm === "approve"
                ? "Approving makes the message eligible for sending. It is NOT sent automatically — you send it explicitly afterwards."
                : "Rejecting marks the draft as rejected. It will not be sent."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirm(null)}>
              Cancel
            </Button>
            <Button
              variant={confirm === "approve" ? "success" : "destructive"}
              onClick={() => {
                if (confirm === "approve") approve.mutate(dirty ? body : undefined);
                else reject.mutate(undefined);
                setConfirm(null);
                setEditing(false);
              }}
            >
              {confirm === "approve" ? "Approve" : "Reject"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-muted-foreground">{k}</dt>
      <dd className="truncate font-mono text-xs">{v}</dd>
    </div>
  );
}
