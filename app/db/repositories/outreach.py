from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.db.models.enums import (
    OutreachChannel,
    OutreachEventType,
    OutreachStatus,
    ProspectStatus,
)
from app.db.models.outreach import AuditEvent, OutreachEvent, OutreachMessage
from app.db.models.prospect import Prospect

log = get_logger(__name__)

# a prospect should not receive the same channel again within this window
_DUPLICATE_WINDOW_DAYS = 30


class OutreachRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def recent_message(
        self, prospect_id: str, channel: OutreachChannel
    ) -> OutreachMessage | None:
        cutoff = datetime.now(UTC) - timedelta(days=_DUPLICATE_WINDOW_DAYS)
        stmt = (
            select(OutreachMessage)
            .where(
                OutreachMessage.prospect_id == prospect_id,
                OutreachMessage.channel == channel.value,
                OutreachMessage.created_at >= cutoff,
                OutreachMessage.status.in_(
                    [OutreachStatus.APPROVED.value, OutreachStatus.SENT.value,
                     OutreachStatus.PENDING_APPROVAL.value]
                ),
            )
            .order_by(desc(OutreachMessage.created_at))
            .limit(1)
        )
        return (await self.s.execute(stmt)).scalars().first()

    async def create(
        self,
        *,
        prospect_id: str,
        evaluation_run_id: str | None,
        channel: OutreachChannel,
        strategy: dict,
        subject: str | None,
        body: str,
        to_address: str | None,
        prompt_version: str,
        llm_meta: dict,
        evidence_ids: list[str],
        status: OutreachStatus = OutreachStatus.PENDING_APPROVAL,
    ) -> OutreachMessage:
        msg = OutreachMessage(
            prospect_id=prospect_id,
            evaluation_run_id=evaluation_run_id,
            channel=channel.value,
            status=status.value,
            strategy=strategy,
            subject=subject,
            body=body,
            to_address=to_address,
            prompt_version=prompt_version,
            llm_meta=llm_meta,
            evidence_ids=evidence_ids,
        )
        self.s.add(msg)
        await self.s.flush()
        await self._event(msg.id, OutreachEventType.DRAFTED, {"channel": channel.value})
        await self._audit("outreach_message", msg.id, "message generated",
                          {"channel": channel.value, "status": status.value})
        return msg

    async def get(self, message_id: str) -> OutreachMessage | None:
        stmt = (
            select(OutreachMessage)
            .where(OutreachMessage.id == message_id)
            .options(selectinload(OutreachMessage.events))
        )
        return (await self.s.execute(stmt)).scalars().first()

    async def approve(self, msg: OutreachMessage, *, actor: str, edited_body: str | None) -> None:
        if edited_body and edited_body.strip() and edited_body != msg.body:
            msg.edited_body = edited_body
            await self._event(msg.id, OutreachEventType.EDITED, {"by": actor})
        msg.status = OutreachStatus.APPROVED.value
        msg.approved_at = datetime.now(UTC)
        msg.approved_by = actor
        await self._event(msg.id, OutreachEventType.APPROVED, {"by": actor})
        await self._audit("outreach_message", msg.id, "message approved", {"by": actor})
        prospect = await self.s.get(Prospect, msg.prospect_id)
        if prospect and prospect.status == ProspectStatus.OUTREACH_DRAFTED.value:
            prospect.status = ProspectStatus.OUTREACH_APPROVED.value
        await self.s.flush()

    async def reject(self, msg: OutreachMessage, *, actor: str, reason: str | None) -> None:
        msg.status = OutreachStatus.REJECTED.value
        msg.rejected_reason = reason
        await self._event(msg.id, OutreachEventType.REJECTED, {"by": actor, "reason": reason})
        await self._audit("outreach_message", msg.id, "message rejected", {"by": actor})
        await self.s.flush()

    async def mark_sent(
        self, msg: OutreachMessage, *, provider: str, reference: str | None, follow_up_days: int
    ) -> None:
        msg.status = OutreachStatus.SENT.value
        msg.sent_at = datetime.now(UTC)
        msg.send_provider = provider
        msg.send_reference = reference
        msg.next_follow_up_at = datetime.now(UTC) + timedelta(days=follow_up_days)
        await self._event(msg.id, OutreachEventType.SENT, {"provider": provider})
        await self._audit("outreach_message", msg.id, "message sent", {"provider": provider})
        prospect = await self.s.get(Prospect, msg.prospect_id)
        if prospect:
            prospect.status = ProspectStatus.CONTACTED.value
            prospect.last_contacted_at = datetime.now(UTC)
        await self.s.flush()

    async def _event(self, message_id: str, kind: OutreachEventType, detail: dict) -> None:
        self.s.add(
            OutreachEvent(
                message_id=message_id, event_type=kind.value, detail=detail,
                occurred_at=datetime.now(UTC),
            )
        )

    async def _audit(self, entity_type: str, entity_id: str, action: str, detail: dict) -> None:
        self.s.add(
            AuditEvent(entity_type=entity_type, entity_id=entity_id, action=action, detail=detail)
        )

    async def list_for_prospect(self, prospect_id: str) -> list[OutreachMessage]:
        stmt = (
            select(OutreachMessage)
            .where(OutreachMessage.prospect_id == prospect_id)
            .order_by(desc(OutreachMessage.created_at))
            .options(selectinload(OutreachMessage.events))
        )
        return list((await self.s.execute(stmt)).scalars())

    async def due_followups(self, limit: int = 50) -> list[OutreachMessage]:
        now = datetime.now(UTC)
        stmt = (
            select(OutreachMessage)
            .where(
                OutreachMessage.status == OutreachStatus.SENT.value,
                OutreachMessage.next_follow_up_at.is_not(None),
                OutreachMessage.next_follow_up_at <= now,
                OutreachMessage.reply_status.is_(None),
            )
            .limit(limit)
        )
        return list((await self.s.execute(stmt)).scalars())
