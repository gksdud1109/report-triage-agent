"""JetStream 후속 소비자 카운터 조회 API.

consumer 프로세스가 누적한 `event_metrics` 테이블을 그대로 노출한다.
"publish만 하지 않고 후속 소비자가 실제로 읽었다"를 한 번의 GET으로
보여주는 게 유일한 목적이라 필터·페이지네이션은 의도적으로 없다.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.db.models import EventMetric

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/events")
async def list_event_metrics(
    session: AsyncSession = Depends(get_session),
) -> dict:
    rows = (
        await session.execute(select(EventMetric).order_by(EventMetric.subject))
    ).scalars().all()
    return {
        "items": [
            {
                "subject": row.subject,
                "count": row.count,
                "last_seen_at": row.last_seen_at,
            }
            for row in rows
        ]
    }
