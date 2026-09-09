from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import ResearchRunStatus


class ResearchRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "research_runs"

    prospect_id: Mapped[str] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ResearchRunStatus.RUNNING.value
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sources_used: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # deterministic, structured research output (not AI interpretation)
    website_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    website_final_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    signals: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    social_profiles: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    error_code: Mapped[str | None] = mapped_column(String(48), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    evidence: Mapped[list[Evidence]] = relationship(
        back_populates="research_run", cascade="all, delete-orphan"
    )


class Evidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single objective observation with provenance. Referenced by AI outputs via id."""

    __tablename__ = "evidence"

    research_run_id: Mapped[str] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prospect_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)  # provider name
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    observation: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    data_origin: Mapped[str] = mapped_column(String(16), nullable=False, default="VERIFIED")
    extra: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    research_run: Mapped[ResearchRun] = relationship(back_populates="evidence")
