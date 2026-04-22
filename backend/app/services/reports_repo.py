from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.ids import new_classification_id, new_queue_item_id
from app.db.models import Report, ReportClassification, ReviewQueueItem
from app.schemas.reports import ReportCreateRequest


async def create_report(session: AsyncSession, report_id: str, payload: ReportCreateRequest) -> Report:
    report = Report(
        id=report_id,
        reporter_id=payload.reporter_id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        reason_code=payload.reason_code,
        description=payload.description,
        source_channel=payload.source_channel,
        report_metadata=payload.metadata or {},
        status="queued",
    )
    session.add(report)
    await session.flush()
    return report


async def get_report(session: AsyncSession, report_id: str) -> Report | None:
    stmt = (
        select(Report)
        .options(selectinload(Report.classification), selectinload(Report.queue_item))
        .where(Report.id == report_id)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def update_report_status(session: AsyncSession, report_id: str, status: str) -> None:
    report = await session.get(Report, report_id)
    if report is None:
        raise LookupError(f"report not found: {report_id}")
    report.status = status
    report.updated_at = datetime.now(timezone.utc)


async def reset_report_for_reprocess(session: AsyncSession, report_id: str) -> Report:
    report = await session.get(Report, report_id)
    if report is None:
        raise LookupError(f"report not found: {report_id}")
    report.status = "queued"
    report.updated_at = datetime.now(timezone.utc)
    return report


async def upsert_classification(
    session: AsyncSession,
    *,
    report_id: str,
    category: str,
    priority: str,
    requires_review: bool,
    confidence: float,
    reasoning_summary: str,
    routed_queue: str,
) -> ReportClassification:
    stmt = select(ReportClassification).where(ReportClassification.report_id == report_id)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing is None:
        existing = ReportClassification(
            id=new_classification_id(),
            report_id=report_id,
            category=category,
            priority=priority,
            requires_review=requires_review,
            confidence=confidence,
            reasoning_summary=reasoning_summary,
            routed_queue=routed_queue,
        )
        session.add(existing)
    else:
        existing.category = category
        existing.priority = priority
        existing.requires_review = requires_review
        existing.confidence = confidence
        existing.reasoning_summary = reasoning_summary
        existing.routed_queue = routed_queue
        existing.updated_at = now
    await session.flush()
    return existing


async def upsert_queue_item(
    session: AsyncSession,
    *,
    report_id: str,
    queue_name: str,
) -> ReviewQueueItem:
    stmt = select(ReviewQueueItem).where(ReviewQueueItem.report_id == report_id)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing is None:
        existing = ReviewQueueItem(
            id=new_queue_item_id(),
            report_id=report_id,
            queue_name=queue_name,
            queue_status="pending",
        )
        session.add(existing)
    else:
        existing.queue_name = queue_name
        existing.queue_status = "pending"
        existing.assigned_to = None
        existing.enqueued_at = now
        existing.updated_at = now
    await session.flush()
    return existing


async def list_queue_items(
    session: AsyncSession,
    *,
    queue_name: str,
    status: str | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[tuple[ReviewQueueItem, ReportClassification | None]], str | None]:
    stmt = (
        select(ReviewQueueItem, ReportClassification)
        .join(
            ReportClassification,
            ReportClassification.report_id == ReviewQueueItem.report_id,
            isouter=True,
        )
        .where(ReviewQueueItem.queue_name == queue_name)
        .order_by(ReviewQueueItem.enqueued_at.desc(), ReviewQueueItem.id.desc())
    )
    if status is not None:
        stmt = stmt.where(ReviewQueueItem.queue_status == status)
    if cursor is not None:
        stmt = stmt.where(ReviewQueueItem.id < cursor)
    stmt = stmt.limit(limit + 1)

    rows = (await session.execute(stmt)).all()
    has_next = len(rows) > limit
    rows = rows[:limit]
    next_cursor = rows[-1][0].id if has_next and rows else None
    return [(r[0], r[1]) for r in rows], next_cursor
