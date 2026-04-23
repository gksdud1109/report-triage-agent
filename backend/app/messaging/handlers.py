"""JetStream 이벤트 핸들러.

consumer 프로세스가 NATS에서 메시지를 받아 디코드한 뒤 호출한다.
부수효과는 `record_event` 한 함수로 격리되어 있어 단위 테스트가 쉽다.

설계 의도:
- 핸들러는 "어떤 subject가 들어왔는가"만 본다. payload 본문은 로깅용으로만
  살짝 들여다본다. 카운트가 핵심이라 schema 변경에 강건하다.
- DB write는 `INSERT ... ON CONFLICT DO UPDATE`로 1쿼리 upsert. consumer가
  중복으로 fetch해도(at-least-once) 카운트만 증가하지 row 충돌은 없다.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EventMetric
from app.messaging.streams import SUBJECT_QUEUE_ROUTED, SUBJECT_REPORT_TRIAGED

logger = logging.getLogger(__name__)


# subject 화이트리스트. 정의된 subject만 처리하고 나머지는 무시한다.
KNOWN_SUBJECTS: frozenset[str] = frozenset(
    {SUBJECT_REPORT_TRIAGED, SUBJECT_QUEUE_ROUTED}
)


async def record_event(session: AsyncSession, subject: str, *, now: datetime | None = None) -> None:
    """주어진 subject 카운터를 +1 한다 (단일 SQL upsert).

    멱등이 아니라 누적이다. consumer가 같은 메시지를 다시 가져오면
    카운트가 한 번 더 오른다 (JetStream at-least-once 의미와 합치).
    """
    timestamp = now or datetime.now(timezone.utc)
    stmt = pg_insert(EventMetric).values(
        subject=subject, count=1, last_seen_at=timestamp
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[EventMetric.subject],
        set_={
            "count": EventMetric.count + 1,
            "last_seen_at": timestamp,
        },
    )
    await session.execute(stmt)


def decode_subject(raw_subject: str, payload: bytes) -> str | None:
    """들어온 message의 subject가 알려진 것인지 판별한다.

    payload는 일부러 검증하지 않는다 (스키마 drift 흡수). 다만 디코드 가능
    여부만 확인해 깨진 메시지는 ack 대상에서 제외하고 싶을 때 호출자가
    분기할 수 있게 None을 돌려준다.
    """
    if raw_subject not in KNOWN_SUBJECTS:
        logger.warning("ignoring unknown subject: %s", raw_subject)
        return None
    try:
        json.loads(payload)
    except (ValueError, UnicodeDecodeError) as err:
        logger.warning("malformed payload on %s: %s", raw_subject, err)
        return None
    return raw_subject
