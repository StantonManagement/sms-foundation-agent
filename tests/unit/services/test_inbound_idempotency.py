import asyncio

import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.models import Base, SmsMessage
from src.services.sms_inbound import SmsInboundService


@pytest.mark.asyncio
async def test_service_idempotency_inserts_once_then_duplicates():
    # In-memory SQLite shared across connections
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )

    async with session_maker() as session:
        service = SmsInboundService()
        payload = {"MessageSid": "SM123"}

        res1 = await service.handle_inbound(payload, session, request_id="r1")
        assert res1["processed"] is True
        assert res1["duplicate"] is False

        # second attempt (duplicate)
        res2 = await service.handle_inbound(payload, session, request_id="r2")
        assert res2["processed"] is False
        assert res2["duplicate"] is True

        # DB should have exactly one row
        count_stmt = select(func.count(SmsMessage.id))
        result = await session.execute(count_stmt)
        (count,) = result.one()
        assert count == 1

