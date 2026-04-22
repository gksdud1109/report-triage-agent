import asyncio
import logging

from temporalio.client import Client

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_client: Client | None = None


async def get_client(max_attempts: int = 10, base_delay: float = 0.5) -> Client:
    """공용 Temporal 클라이언트를 반환한다. 첫 호출 시에만 실제로 연결한다.

    Temporal 서버와의 기동 레이스를 흡수하기 위해 지수 백오프로 재시도한다.
    """
    global _client
    if _client is not None:
        return _client

    settings = get_settings()
    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            _client = await Client.connect(
                settings.temporal_host, namespace=settings.temporal_namespace
            )
            return _client
        except RuntimeError as err:
            last_err = err
            delay = min(base_delay * (2 ** (attempt - 1)), 5.0)
            logger.warning(
                "temporal connect attempt %s/%s failed: %s; retry in %.1fs",
                attempt, max_attempts, err, delay,
            )
            await asyncio.sleep(delay)

    raise RuntimeError(
        f"could not connect to Temporal at {settings.temporal_host}: {last_err}"
    )


async def close() -> None:
    global _client
    _client = None
