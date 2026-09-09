from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import ProspectStatus, QualityStatus, RecordKind


class Prospect(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "prospects"
    __table_args__ = (
        UniqueConstraint("canonical_domain", name="uq_prospects_canonical_domain"),
        UniqueConstraint("google_place_id", name="uq_prospects_google_place_id"),
    )

    business_name: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)

    industry: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    phone: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    phone_e164: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    website: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    canonical_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)

    google_place_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ProspectStatus.DISCOVERED.value, index=True
    )
    quality_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=QualityStatus.OK.value
    )
    record_kind: Mapped[str] = mapped_column(
        String(8), nullable=False, default=RecordKind.REAL.value
    )

    # provider-specific extras that don't deserve columns
    provider_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    discovery_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    last_researched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_evaluated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_contacted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    sources: Mapped[list[ProspectSource]] = relationship(
        back_populates="prospect", cascade="all, delete-orphan"
    )
    contacts: Mapped[list[ProspectContact]] = relationship(
        back_populates="prospect", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Prospect {self.id} {self.business_name!r}>"


class ProspectSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Provenance: which provider/query surfaced this prospect, and what it said."""

    __tablename__ = "prospect_sources"
    __table_args__ = (
        UniqueConstraint(
            "prospect_id", "provider", "source_identity", name="uq_prospect_source_identity"
        ),
    )

    prospect_id: Mapped[str] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    source_identity: Mapped[str] = mapped_column(String(512), nullable=False)  # dedupe key per source
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    search_query: Mapped[str | None] = mapped_column(String(512), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    prospect: Mapped[Prospect] = relationship(back_populates="sources")


class ProspectContact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "prospect_contacts"

    prospect_id: Mapped[str] = mapped_column(
        ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)  # phone|email|whatsapp|contact_page
    value: Mapped[str] = mapped_column(String(1024), nullable=False)
    data_origin: Mapped[str] = mapped_column(String(16), nullable=False, default="RAW")
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    verified: Mapped[bool] = mapped_column(default=False, nullable=False)

    prospect: Mapped[Prospect] = relationship(back_populates="contacts")
