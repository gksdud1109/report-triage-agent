"""FastAPI 앱 팩토리 및 lifespan.

앱은 얇게 유지한다: 요청 처리와 Temporal workflow 시작만 담당한다.
장기 실행 triage 로직은 모두 Temporal activity에서 수행된다.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine
from app.messaging import nats_client
from app.temporal import client as temporal_client

# create_all 이전에 Base.metadata가 모델을 인식하도록 import만 해둔다.
from app.db import models  # noqa: F401

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = get_settings()
    logger.info("starting api; db=%s nats=%s temporal=%s",
                settings.database_url, settings.nats_url, settings.temporal_host)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await nats_client.connect()
    await temporal_client.get_client()

    try:
        yield
    finally:
        await nats_client.close()
        await temporal_client.close()
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="Report Triage Agent", version="0.1.0", lifespan=lifespan)
    app.include_router(health_router)
    return app


app = create_app()
