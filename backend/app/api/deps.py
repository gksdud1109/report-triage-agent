from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client

from app.db.session import session_scope
from app.temporal import client as temporal_client


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_scope() as session:
        yield session


async def get_temporal_client() -> Client:
    return await temporal_client.get_client()
