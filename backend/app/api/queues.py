"""큐별 신고 목록 조회 API."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.schemas.queue import QueueItemPayload, QueueListResponse, QueueStatus
from app.services import reports_repo

router = APIRouter(prefix="/queues", tags=["queues"])


@router.get("/{queue_name}/reports", response_model=QueueListResponse)
async def list_queue_reports(
    queue_name: str,
    status: QueueStatus | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> QueueListResponse:
    """큐 아이템과 분류 결과를 조인해서 요약 목록으로 반환한다.

    페이지네이션은 id desc 키셋 기반.
    """
    pairs, next_cursor = await reports_repo.list_queue_items(
        session,
        queue_name=queue_name,
        status=status,
        limit=limit,
        cursor=cursor,
    )

    items: list[QueueItemPayload] = []
    for queue_item, classification in pairs:
        items.append(
            QueueItemPayload(
                report_id=queue_item.report_id,
                queue_status=queue_item.queue_status,
                category=classification.category if classification else "unknown",
                priority=classification.priority if classification else "low",
                requires_review=classification.requires_review if classification else False,
                enqueued_at=queue_item.enqueued_at,
            )
        )

    return QueueListResponse(queue_name=queue_name, items=items, next_cursor=next_cursor)
