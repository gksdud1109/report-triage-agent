"""Triage 이벤트 publisher.

publisher-side dedup:
 publish 활동이 워크플로 retry로 다시 호출될 때 같은 report에 대해 같은
 메시지가 두 번 publish되는 것을 막는다. JetStream `Nats-Msg-Id` 헤더와
 stream의 `duplicate_window`(streams.py)가 짝을 이뤄 dedup window 내 중복을
 제거한다. 이게 없으면 publish 부분 실패 시 재시도가 첫 번째 메시지를 N회
 누적시켜 `event_metrics` 카운터가 사실과 어긋난다.
"""

import logging

from app.messaging import nats_client
from app.messaging.streams import SUBJECT_QUEUE_ROUTED, SUBJECT_REPORT_TRIAGED
from app.schemas.events import QueueRoutedEvent, TriagedEvent

logger = logging.getLogger(__name__)


def _msg_id(subject: str, report_id: str) -> str:
    """`Nats-Msg-Id` 헤더 값. (subject, report_id) 조합이 한 번의 분류 결과당 유일.

    재처리(reprocess)는 의도적으로 새 dedup window가 필요하지 않다 — duplicate_window
    안에서는 같은 report의 재발행이 무시되는 게 의도다. window 밖이면 자연스럽게
    새 메시지로 카운트.
    """
    return f"{subject}:{report_id}"


async def publish_triaged(event: TriagedEvent) -> None:
    js = nats_client.jetstream()
    payload = event.model_dump_json().encode("utf-8")
    ack = await js.publish(
        SUBJECT_REPORT_TRIAGED,
        payload,
        headers={"Nats-Msg-Id": _msg_id(SUBJECT_REPORT_TRIAGED, event.report_id)},
    )
    logger.info(
        "published %s seq=%s duplicate=%s",
        SUBJECT_REPORT_TRIAGED, ack.seq, getattr(ack, "duplicate", False),
    )


async def publish_queue_routed(event: QueueRoutedEvent) -> None:
    js = nats_client.jetstream()
    payload = event.model_dump_json().encode("utf-8")
    ack = await js.publish(
        SUBJECT_QUEUE_ROUTED,
        payload,
        headers={"Nats-Msg-Id": _msg_id(SUBJECT_QUEUE_ROUTED, event.report_id)},
    )
    logger.info(
        "published %s seq=%s duplicate=%s",
        SUBJECT_QUEUE_ROUTED, ack.seq, getattr(ack, "duplicate", False),
    )
