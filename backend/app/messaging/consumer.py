"""JetStream 후속 소비자.

별도 프로세스로 동작한다 (`python -m app.messaging`). Temporal worker와
이벤트 루프·종료 시그널을 공유하지 않는다 — "후속 시스템 경계로서의 NATS"
라는 README의 의사결정을 프로세스 경계로 실체화하는 게 의도다.

동작:
- `report.triaged` 와 `queue.routed` 두 subject에 각각 durable consumer를
  하나씩 등록한다 (push subscription, manual ack).
- 메시지 수신 시 `event_metrics` 카운터를 +1 한다.
- SIGINT/SIGTERM 받으면 graceful drain 후 종료.

failure model:
- handler 실패는 ack를 미루고 NATS가 redeliver. 일정 횟수 후 dead-letter.
- DB 연결 끊김은 컨테이너 재시작에 맡긴다 (compose `restart: unless-stopped`).
"""

from __future__ import annotations

import asyncio
import logging
import signal
from typing import Awaitable, Callable

from app.core.config import get_settings
from app.db.session import session_scope
from app.messaging import nats_client
from app.messaging.handlers import decode_subject, record_event
from app.messaging.streams import SUBJECT_QUEUE_ROUTED, SUBJECT_REPORT_TRIAGED

logger = logging.getLogger(__name__)


DURABLE_TRIAGED = "triage-metrics-triaged"
DURABLE_ROUTED = "triage-metrics-routed"


def _make_handler(subject_label: str) -> Callable[[object], Awaitable[None]]:
    """주어진 subject에 대한 NATS 메시지 콜백을 만든다.

    클로저로 라벨을 넣어서 로깅할 때 어느 핸들러인지 추적 가능하게 한다.
    """

    async def _handler(msg) -> None:  # type: ignore[no-untyped-def]
        subject = decode_subject(msg.subject, msg.data)
        if subject is None:
            # 알 수 없는 subject나 깨진 payload는 그냥 ack 처리해 다시 안 받게 한다.
            await msg.ack()
            return
        try:
            async with session_scope() as session:
                await record_event(session, subject)
        except Exception:
            logger.exception(
                "failed to record event subject=%s seq=%s; will redeliver",
                subject_label, msg.metadata.sequence.stream,
            )
            # ack 안 하면 JetStream이 redeliver 한다.
            return
        await msg.ack()
        logger.info(
            "consumed subject=%s stream_seq=%s",
            subject_label, msg.metadata.sequence.stream,
        )

    return _handler


async def _run() -> None:
    settings = get_settings()
    js = await nats_client.connect()

    await js.subscribe(
        SUBJECT_REPORT_TRIAGED,
        durable=DURABLE_TRIAGED,
        cb=_make_handler(SUBJECT_REPORT_TRIAGED),
        manual_ack=True,
    )
    await js.subscribe(
        SUBJECT_QUEUE_ROUTED,
        durable=DURABLE_ROUTED,
        cb=_make_handler(SUBJECT_QUEUE_ROUTED),
        manual_ack=True,
    )

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    logger.info(
        "jetstream consumer started; stream=%s durables=[%s,%s]",
        settings.nats_stream, DURABLE_TRIAGED, DURABLE_ROUTED,
    )

    await stop.wait()
    logger.info("jetstream consumer stopping")
    await nats_client.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(_run())


if __name__ == "__main__":
    main()
