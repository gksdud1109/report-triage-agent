import logging

from app.messaging import nats_client
from app.messaging.streams import SUBJECT_QUEUE_ROUTED, SUBJECT_REPORT_TRIAGED
from app.schemas.events import QueueRoutedEvent, TriagedEvent

logger = logging.getLogger(__name__)


async def publish_triaged(event: TriagedEvent) -> None:
    js = nats_client.jetstream()
    payload = event.model_dump_json().encode("utf-8")
    ack = await js.publish(SUBJECT_REPORT_TRIAGED, payload)
    logger.info("published %s seq=%s", SUBJECT_REPORT_TRIAGED, ack.seq)


async def publish_queue_routed(event: QueueRoutedEvent) -> None:
    js = nats_client.jetstream()
    payload = event.model_dump_json().encode("utf-8")
    ack = await js.publish(SUBJECT_QUEUE_ROUTED, payload)
    logger.info("published %s seq=%s", SUBJECT_QUEUE_ROUTED, ack.seq)
