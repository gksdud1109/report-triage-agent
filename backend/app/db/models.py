from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    reporter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_channel: Mapped[str] = mapped_column(String(32), nullable=False)
    report_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    classification: Mapped["ReportClassification | None"] = relationship(
        back_populates="report", uselist=False, cascade="all, delete-orphan"
    )
    queue_item: Mapped["ReviewQueueItem | None"] = relationship(
        back_populates="report", uselist=False, cascade="all, delete-orphan"
    )


class ReportClassification(Base):
    __tablename__ = "report_classifications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    report_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("reports.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    requires_review: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reasoning_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    routed_queue: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    report: Mapped[Report] = relationship(back_populates="classification")


class ReviewQueueItem(Base):
    __tablename__ = "review_queue_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    report_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("reports.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    queue_name: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    queue_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    assigned_to: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enqueued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    report: Mapped[Report] = relationship(back_populates="queue_item")
