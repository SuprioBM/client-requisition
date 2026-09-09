from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import OutreachStatus


class OutreachMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "outreach_messages"

    prospect_id: Mapped[str] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evaluation_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    channel: Mapped[str] = mapped_column(String(16), nullable=False)  # EMAIL | WHATSAPP
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=OutreachStatus.PENDING_APPROVAL.value, index=True
    )

    strategy: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    edited_body: Mapped[str | None] = mapped_column(Text, nullable=True)

    to_address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")
    llm_meta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rejected_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    send_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    send_reference: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # follow-up tracking
    follow_up_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reply_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    events: Mapped[list[OutreachEvent]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )

    @property
    def final_body(self) -> str:
        return self.edited_body or self.body


class OutreachEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "outreach_events"

    message_id: Mapped[str] = mapped_column(
        ForeignKey("outreach_messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    message: Mapped[OutreachMessage] = relationship(back_populates="events")


class AuditEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_events"

    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False, default="system")
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
