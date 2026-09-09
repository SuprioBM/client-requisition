from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.db.models.enums import OutreachChannel, OutreachStatus
from app.db.models.outreach import OutreachMessage
from app.db.models.prospect import Prospect
from app.db.repositories.outreach import OutreachRepository
from app.db.session import session_scope
from app.services import outreach_service


async def _sent_message(days_ago_followup: int = 1) -> str:
    async with session_scope() as s:
        p = Prospect(business_name="X", normalized_name="x", city="Dhaka", country="Bangladesh")
        s.add(p)
        await s.flush()
        m = OutreachMessage(
            prospect_id=p.id, channel=OutreachChannel.EMAIL.value,
            status=OutreachStatus.SENT.value, body="hi", to_address="a@b.c",
            sent_at=datetime.now(UTC) - timedelta(days=10),
            next_follow_up_at=datetime.now(UTC) - timedelta(days=days_ago_followup),
        )
        s.add(m)
        await s.flush()
        return m.id


async def test_due_followup_is_marked_and_rescheduled():
    mid = await _sent_message()
    res = await outreach_service.process_followups()
    assert mid in res["followups_due"]
    async with session_scope() as s:
        m = await s.get(OutreachMessage, mid)
        assert m.follow_up_count == 1
        nxt = m.next_follow_up_at.replace(tzinfo=UTC) if m.next_follow_up_at.tzinfo is None else m.next_follow_up_at
        assert nxt > datetime.now(UTC)


async def test_followups_stop_after_max():
    mid = await _sent_message()
    for _ in range(5):
        async with session_scope() as s:
            m = await s.get(OutreachMessage, mid)
            m.next_follow_up_at = datetime.now(UTC) - timedelta(days=1)
        await outreach_service.process_followups()
    async with session_scope() as s:
        m = await s.get(OutreachMessage, mid)
        assert m.follow_up_count <= 2  # OUTREACH_MAX_FOLLOW_UPS default
        assert m.next_follow_up_at is None


async def test_reply_stops_followups():
    mid = await _sent_message()
    await outreach_service.record_reply(mid, replied=True)
    res = await outreach_service.process_followups()
    assert mid not in res["followups_due"]


async def test_duplicate_send_blocked():
    async with session_scope() as s:
        p = Prospect(business_name="Y", normalized_name="y", city="Dhaka", country="Bangladesh")
        s.add(p)
        await s.flush()
        repo = OutreachRepository(s)
        already = await repo.create(
            prospect_id=p.id, evaluation_run_id=None, channel=OutreachChannel.EMAIL,
            strategy={}, subject="s", body="b", to_address="a@b.c", prompt_version="v1",
            llm_meta={}, evidence_ids=[], status=OutreachStatus.SENT,
        )
        already.sent_at = datetime.now(UTC)
        new = await repo.create(
            prospect_id=p.id, evaluation_run_id=None, channel=OutreachChannel.EMAIL,
            strategy={}, subject="s2", body="b2", to_address="a@b.c", prompt_version="v1",
            llm_meta={}, evidence_ids=[], status=OutreachStatus.APPROVED,
        )
        new_id = new.id

    from app.core.exceptions import OutreachError

    try:
        await outreach_service.send(new_id, actor="t")
        raised = False
    except OutreachError as exc:
        raised = exc.code.value == "DUPLICATE_OUTREACH"
    assert raised
