"""Temporal worker 엔트리포인트.

실행:  python -m app.temporal.worker

기동 순서:
 1. NATS 연결 (activity가 이벤트 발행 시 사용)
 2. Temporal 클라이언트 연결
 3. workflow + activity 등록 후 task queue 소비 시작
"""

import asyncio
import logging
import signal

from temporalio.worker import Worker

from app.core.config import get_settings
from app.messaging import nats_client
from app.temporal import client as temporal_client
from app.temporal.activities import ALL_ACTIVITIES
from app.temporal.workflows import ReportTriageWorkflow

logger = logging.getLogger(__name__)


async def _run() -> None:
    settings = get_settings()

    await nats_client.connect()
    client = await temporal_client.get_client()

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[ReportTriageWorkflow],
        activities=ALL_ACTIVITIES,
    )

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    logger.info(
        "temporal worker started; task_queue=%s", settings.temporal_task_queue
    )

    async with worker:
        await stop.wait()

    logger.info("temporal worker stopping")
    await nats_client.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(_run())


if __name__ == "__main__":
    main()
