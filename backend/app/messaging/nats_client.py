import asyncio
import logging

import nats
from nats.aio.client import Client as NATSClient
from nats.errors import NoServersError
from nats.js import JetStreamContext
from nats.js.api import StreamConfig
from nats.js.errors import NotFoundError

from app.core.config import get_settings
from app.messaging.streams import DUPLICATE_WINDOW_SECONDS, STREAM_SUBJECTS

logger = logging.getLogger(__name__)

_nc: NATSClient | None = None
_js: JetStreamContext | None = None


async def connect(max_attempts: int = 10, base_delay: float = 0.5) -> JetStreamContext:
    """NATS에 연결하고 JetStream 스트림 존재를 보장한다.

    컨테이너 기동 레이스(앱이 nats보다 먼저 떠서 연결 실패)를 흡수하기 위해
    `NoServersError`에 대해 지수 백오프로 재시도한다.
    """
    global _nc, _js
    if _js is not None:
        return _js

    settings = get_settings()
    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            _nc = await nats.connect(settings.nats_url)
            break
        except (NoServersError, OSError) as err:
            last_err = err
            delay = min(base_delay * (2 ** (attempt - 1)), 5.0)
            logger.warning(
                "nats connect attempt %s/%s failed: %s; retry in %.1fs",
                attempt, max_attempts, err, delay,
            )
            await asyncio.sleep(delay)
    else:
        raise RuntimeError(f"could not connect to NATS at {settings.nats_url}: {last_err}")

    assert _nc is not None
    _js = _nc.jetstream()

    # 스트림은 add 또는 update를 멱등하게 적용한다 — duplicate_window 변경이
    # 운영 중에 들어와도 자동 반영된다 (재기동 시 nats_client.connect()에서 호출).
    # nats-py는 duplicate_window를 초 단위 number로 받는다 (timedelta 아님).
    desired = StreamConfig(
        name=settings.nats_stream,
        subjects=STREAM_SUBJECTS,
        duplicate_window=DUPLICATE_WINDOW_SECONDS,
    )
    try:
        await _js.stream_info(settings.nats_stream)
        await _js.update_stream(desired)
        logger.info(
            "updated JetStream stream %s (duplicate_window=%ss)",
            settings.nats_stream, DUPLICATE_WINDOW_SECONDS,
        )
    except NotFoundError:
        await _js.add_stream(desired)
        logger.info(
            "created JetStream stream %s (duplicate_window=%ss)",
            settings.nats_stream, DUPLICATE_WINDOW_SECONDS,
        )

    return _js


async def close() -> None:
    global _nc, _js
    if _nc is not None:
        await _nc.drain()
    _nc = None
    _js = None


def jetstream() -> JetStreamContext:
    if _js is None:
        raise RuntimeError("NATS JetStream not connected; call connect() first")
    return _js
