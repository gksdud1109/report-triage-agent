"""ReportTriageWorkflow에서 사용하는 Temporal activity 모음.

Activity는 얇은 어댑터 역할만 한다:
 - DB 읽기/쓰기: `services.reports_repo`
 - 순수 서비스 호출: `classifier`, `priority`, `review`, `routing`
 - NATS 이벤트 발행: `messaging.events`

기본 Temporal 데이터 컨버터가 처리하도록 각 activity는 JSON 직렬화 가능한
primitive/dict만 주고받는다.
"""

from datetime import datetime, timezone

from temporalio import activity
from temporalio.exceptions import ApplicationError

from app.db.enums import ReportStatus
from app.db.session import session_scope
from app.messaging import events as nats_events
from app.schemas.events import QueueRoutedEvent, TriagedEvent
from app.services import classifier, priority, review, reports_repo, routing


@activity.defn
async def load_report_activity(report_id: str) -> dict:
    async with session_scope() as session:
        report = await reports_repo.get_report(session, report_id)
        if report is None:
            raise ApplicationError(
                f"report not found: {report_id}", type="ReportNotFound", non_retryable=True
            )
        return {
            "report_id": report.id,
            "reason_code": report.reason_code,
            "description": report.description,
            "metadata": report.report_metadata or {},
        }


@activity.defn
async def mark_report_processing_activity(report_id: str) -> None:
    async with session_scope() as session:
        await reports_repo.update_report_status(session, report_id, ReportStatus.PROCESSING)


@activity.defn
async def classify_report_activity(report: dict) -> dict:
    result = classifier.classify_report(
        reason_code=report["reason_code"],
        description=report["description"],
        metadata=report.get("metadata") or {},
    )
    return {
        "category": result.category,
        "confidence": result.confidence,
        "reasoning_summary": result.reasoning_summary,
    }


@activity.defn
async def score_priority_activity(report: dict, category: str) -> str:
    return priority.score_priority(
        category=category,
        description=report["description"],
        metadata=report.get("metadata") or {},
    )


@activity.defn
async def decide_review_activity(category: str, priority_level: str, confidence: float) -> bool:
    return review.decide_requires_review(category, priority_level, confidence)


@activity.defn
async def persist_classification_activity(
    report_id: str,
    category: str,
    priority_level: str,
    requires_review: bool,
    confidence: float,
    reasoning_summary: str,
) -> str:
    routed_queue = routing.route_to_queue(category)
    async with session_scope() as session:
        await reports_repo.upsert_classification(
            session,
            report_id=report_id,
            category=category,
            priority=priority_level,
            requires_review=requires_review,
            confidence=confidence,
            reasoning_summary=reasoning_summary,
            routed_queue=routed_queue,
        )
    return routed_queue


@activity.defn
async def route_queue_activity(report_id: str, queue_name: str) -> None:
    async with session_scope() as session:
        await reports_repo.upsert_queue_item(
            session, report_id=report_id, queue_name=queue_name
        )


@activity.defn
async def publish_triage_events_activity(
    report_id: str,
    category: str,
    priority_level: str,
    requires_review: bool,
    confidence: float,
    queue_name: str,
) -> None:
    now = datetime.now(timezone.utc)
    await nats_events.publish_triaged(
        TriagedEvent(
            report_id=report_id,
            category=category,
            priority=priority_level,
            requires_review=requires_review,
            confidence=confidence,
            occurred_at=now,
        )
    )
    await nats_events.publish_queue_routed(
        QueueRoutedEvent(
            report_id=report_id,
            queue_name=queue_name,
            queue_status="pending",
            occurred_at=now,
        )
    )


@activity.defn
async def mark_report_classified_activity(report_id: str) -> None:
    async with session_scope() as session:
        await reports_repo.update_report_status(session, report_id, ReportStatus.CLASSIFIED)


@activity.defn
async def mark_report_failed_activity(report_id: str) -> None:
    async with session_scope() as session:
        await reports_repo.update_report_status(session, report_id, ReportStatus.FAILED)


ALL_ACTIVITIES = [
    load_report_activity,
    mark_report_processing_activity,
    classify_report_activity,
    score_priority_activity,
    decide_review_activity,
    persist_classification_activity,
    route_queue_activity,
    publish_triage_events_activity,
    mark_report_classified_activity,
    mark_report_failed_activity,
]
