from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, String, Text
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
    # 클라이언트가 동일 페이로드 재시도 시 한 건만 생성되도록 사용. 헤더가
    # 없으면 NULL이고, NULL은 unique 제약에서 서로 다른 값으로 취급되므로
    # 기존 동작(매 요청 새 row)을 깨지 않는다 (PostgreSQL 표준).
    idempotency_key: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
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


class EventMetric(Base):
    """JetStream 이벤트 후속 소비자가 누적하는 단순 카운터.

    consumer 프로세스가 `report.triaged`/`queue.routed`를 받을 때마다
    subject 단위로 +1 한다. "publish만 한다"가 아니라 후속 소비자가
    실제로 읽는다는 사실을 운영 화면(`GET /metrics/events`)에 노출하기
    위해 둔, 의도적으로 얇은 테이블이다.
    """

    __tablename__ = "event_metrics"

    subject: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
