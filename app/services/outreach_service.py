"""Human approval + sending + follow-up tracking for outreach messages."""

from __future__ import annotations

import os
from typing import Any

from app.core.errors import ErrorCode
from app.core.exceptions import NotFoundError, OutreachError
from app.core.logging import get_logger
from app.db.models.enums import OutreachChannel, OutreachEventType, OutreachStatus
from app.db.repositories.outreach import OutreachRepository
from app.db.session import session_scope
from app.outreach.providers import get_outreach_provider

log = get_logger(__name__)

_FOLLOW_UP_DAYS = int(os.environ.get("OUTREACH_FOLLOW_UP_DAYS", "5"))
_MAX_FOLLOW_UPS = int(os.environ.get("OUTREACH_MAX_FOLLOW_UPS", "2"))


async def approve(message_id: str, *, actor: str, edited_body: str | None = None) -> dict[str, Any]:
    async with session_scope() as s:
        repo = OutreachRepository(s)
        msg = await repo.get(message_id)
        if msg is None:
            raise NotFoundError(f"Outreach message {message_id} not found", code=ErrorCode.NOT_FOUND)
        if msg.status not in (OutreachStatus.PENDING_APPROVAL.value, OutreachStatus.DRAFTED.value):
            raise OutreachError(
                f"Message is {msg.status}, cannot approve",
                code=ErrorCode.OUTREACH_NOT_APPROVED,
                http_status=409,
            )
        await repo.approve(msg, actor=actor, edited_body=edited_body)
        return {"id": msg.id, "status": msg.status}


async def reject(message_id: str, *, actor: str, reason: str | None = None) -> dict[str, Any]:
    async with session_scope() as s:
        repo = OutreachRepository(s)
        msg = await repo.get(message_id)
        if msg is None:
            raise NotFoundError(f"Outreach message {message_id} not found", code=ErrorCode.NOT_FOUND)
        await repo.reject(msg, actor=actor, reason=reason)
        return {"id": msg.id, "status": msg.status}


async def send(message_id: str, *, actor: str, override_duplicate: bool = False) -> dict[str, Any]:
    async with session_scope() as s:
        repo = OutreachRepository(s)
        msg = await repo.get(message_id)
        if msg is None:
            raise NotFoundError(f"Outreach message {message_id} not found", code=ErrorCode.NOT_FOUND)
        if msg.status != OutreachStatus.APPROVED.value:
            raise OutreachError(
                "Only APPROVED messages can be sent",
                code=ErrorCode.OUTREACH_NOT_APPROVED,
                http_status=409,
            )
        channel = OutreachChannel(msg.channel)

        if not override_duplicate:
            other = await repo.recent_message(msg.prospect_id, channel)
            if other is not None and other.id != msg.id and other.status == OutreachStatus.SENT.value:
                raise OutreachError(
                    "This prospect already received this outreach type recently",
                    code=ErrorCode.DUPLICATE_OUTREACH,
                    http_status=409,
                )

        provider = await get_outreach_provider(channel)
        result = await provider.send(
            to=msg.to_address, subject=msg.subject, body=msg.final_body
        )
        if result.ok:
            await repo.mark_sent(
                msg, provider=result.provider, reference=result.reference,
                follow_up_days=_FOLLOW_UP_DAYS,
            )
            log.info("outreach.sent", message_id=msg.id, provider=result.provider)
            return {"id": msg.id, "status": OutreachStatus.SENT.value, "provider": result.provider}

        # not configured / failed: do NOT fake success
        msg.status = OutreachStatus.NOT_CONFIGURED.value
        msg.send_provider = result.provider
        await repo._event(  # noqa: SLF001
            msg.id, OutreachEventType.SENT, {"result": "not_configured", "detail": result.detail}
        )
        log.warning("outreach.send.unconfigured", message_id=msg.id, detail=result.detail)
        return {
            "id": msg.id,
            "status": OutreachStatus.NOT_CONFIGURED.value,
            "detail": result.detail,
        }


async def process_followups() -> dict[str, Any]:
    """Mark due follow-ups. Does NOT auto-send: creates a follow-up task signal only."""
    processed: list[str] = []
    async with session_scope() as s:
        repo = OutreachRepository(s)
        due = await repo.due_followups()
        for msg in due:
            if msg.follow_up_count >= _MAX_FOLLOW_UPS:
                await repo._event(msg.id, OutreachEventType.CLOSED,  # noqa: SLF001
                                  {"reason": "max_follow_ups_reached"})
                msg.next_follow_up_at = None
                continue
            msg.follow_up_count += 1
            await repo._event(  # noqa: SLF001
                msg.id, OutreachEventType.FOLLOW_UP_DUE, {"count": msg.follow_up_count}
            )
            from datetime import UTC, datetime, timedelta

            msg.next_follow_up_at = datetime.now(UTC) + timedelta(days=_FOLLOW_UP_DAYS)
            processed.append(msg.id)
    log.info("outreach.followups.processed", count=len(processed))
    return {"followups_due": processed}


async def record_reply(message_id: str, *, replied: bool = True) -> dict[str, Any]:
    async with session_scope() as s:
        repo = OutreachRepository(s)
        msg = await repo.get(message_id)
        if msg is None:
            raise NotFoundError(f"Outreach message {message_id} not found", code=ErrorCode.NOT_FOUND)
        msg.reply_status = "replied" if replied else "no_reply"
        msg.next_follow_up_at = None
        await repo._event(msg.id, OutreachEventType.REPLIED, {})  # noqa: SLF001
        return {"id": msg.id, "reply_status": msg.reply_status}
