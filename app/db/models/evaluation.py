from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EvaluationRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_runs"

    prospect_id: Mapped[str] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    research_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    prompt_version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")
    scoring_version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="RUNNING")
    error_code: Mapped[str | None] = mapped_column(String(48), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # opportunity assessment (AI interpretation, evidence-backed)
    opportunity_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    commercial_potential: Mapped[str | None] = mapped_column(String(16), nullable=True)
    opportunity_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_opportunity: Mapped[bool | None] = mapped_column(nullable=True)

    # scores
    score_problem_severity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_business_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_evidence_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_solution_fit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_contactability: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_total: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    score_breakdown: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    llm_meta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # latency, tokens, status
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    pain_points: Mapped[list[PainPoint]] = relationship(
        back_populates="evaluation_run", cascade="all, delete-orphan"
    )
    solutions: Mapped[list[Solution]] = relationship(
        back_populates="evaluation_run", cascade="all, delete-orphan"
    )


class PainPoint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pain_points"

    evaluation_run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prospect_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    category: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(24), nullable=False)
    evidence_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    severity: Mapped[float | None] = mapped_column(Float, nullable=True)

    evaluation_run: Mapped[EvaluationRun] = relationship(back_populates="pain_points")


class Solution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "solutions"

    evaluation_run_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prospect_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    pain_point_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    service_category: Mapped[str] = mapped_column(String(64), nullable=False)
    service_name: Mapped[str] = mapped_column(String(128), nullable=False)
    why_it_fits: Mapped[str] = mapped_column(Text, nullable=False)
    expected_value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(24), nullable=False)
    fit_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=99)

    evaluation_run: Mapped[EvaluationRun] = relationship(back_populates="solutions")
