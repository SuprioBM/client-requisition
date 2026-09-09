# Outreach

Communicates the opportunity. **No autonomous sending in V1.**

## Strategy → drafts

`generate_outreach_strategy` (LLM) produces `{primary_observation,
primary_problem, primary_solution, value_proposition, tone, call_to_action,
evidence_ids}` focused on the single strongest legitimate opportunity.

Then:
- **Email** (`email_prompt`): personal opening → specific evidence-backed
  observation → problem → proposed solution → realistic value → soft CTA.
  ≤160 words. Banned: generic agency language, "10x", fake stats, fake
  compliments, pretending to be a customer, fabricated urgency.
- **WhatsApp** (`whatsapp_prompt`): ~4–6 short lines, not a copy of the email.

## Human approval (real workflow state)

Drafts are created as `outreach_messages` with status `PENDING_APPROVAL`.
Allowed operator actions:

| Action | Endpoint | Effect |
|---|---|---|
| Approve | `POST /api/v1/outreach/{id}/approve` | `PENDING_APPROVAL → APPROVED` (optional `edited_body`) |
| Reject | `POST /api/v1/outreach/{id}/reject` | `→ REJECTED` with reason |
| Send | `POST /api/v1/outreach/{id}/send` | only if `APPROVED` |

Only `APPROVED` messages can be sent. Every transition writes an
`outreach_events` row and an `audit_events` row.

## Sending (`app/outreach/providers.py`)

`OutreachProvider` interface. V1:
- `NullOutreachProvider` — dev default. Returns `NOT_CONFIGURED`. **Never
  reports a fake `SENT`.**
- `SmtpEmailProvider` — real SMTP, active only when `SMTP_HOST/PORT/FROM` set.
- WhatsApp: no send integration → `NOT_CONFIGURED`.

## Duplicate protection

Before drafting or sending, `OutreachRepository.recent_message` checks for an
`APPROVED|SENT|PENDING_APPROVAL` message of the same channel to the same
prospect within 30 days. Drafting skips it (`blocked_duplicate`); sending raises
`DUPLICATE_OUTREACH` (409) unless `override_duplicate: true`.

## Follow-up tracking

On send, `next_follow_up_at = now + OUTREACH_FOLLOW_UP_DAYS`.
`outreach_service.process_followups()` marks due follow-ups (event
`follow_up_due`), enforces `OUTREACH_MAX_FOLLOW_UPS`, and stops once a reply is
recorded (`record_reply`). Follow-ups are **not** auto-sent.

Tracked lifecycle: `drafted → approved → sent → delivered → opened → replied →
follow_up_due → follow_up_sent → closed` / `rejected`. Delivered/opened/replied
are only set when a provider actually reports them.
