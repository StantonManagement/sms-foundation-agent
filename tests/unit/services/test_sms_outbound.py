from __future__ import annotations

import anyio
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.adapters.twilio_client import TwilioClient, TwilioError
from src.db.models import Base, SmsMessage
from src.services.sms_outbound import SmsOutboundService


class _FakeTwilio(TwilioClient):
    def __init__(self, sid: str | None = "SM-SVC", fail: bool = False):  # type: ignore[no-untyped-def]
        self._sid = sid
        self._fail = fail

    async def send_sms(self, to: str, body: str, *, from_number: str | None = None) -> str:  # type: ignore[override]
        if self._fail:
            raise TwilioError("boom")
        return self._sid or "SM-SVC"


@pytest.mark.asyncio
async def test_service_happy_path_updates_status():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:  # type: ignore[misc]
        svc = SmsOutboundService(session, _FakeTwilio("SM-XYZ"))
        result = await svc.send("+15555550188", "Hi!", request_id="req-1")
        assert result.twilio_sid == "SM-XYZ"

        # Inspect DB
        stmt = select(SmsMessage).where(SmsMessage.id == int(result.id))
        res = await session.execute(stmt)
        msg = res.scalar_one()
        assert msg.delivery_status in ("queued", "sent")
        assert msg.twilio_sid == "SM-XYZ"


@pytest.mark.asyncio
async def test_service_provider_error_marks_failed():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:  # type: ignore[misc]
        svc = SmsOutboundService(session, _FakeTwilio(fail=True))
        with pytest.raises(TwilioError):
            await svc.send("+15555550177", "Yo", request_id="req-2")

        # Check last message is failed
        stmt = select(SmsMessage).order_by(SmsMessage.id.desc()).limit(1)
        res = await session.execute(stmt)
        msg = res.scalar_one()
        assert msg.delivery_status == "failed"
        assert msg.twilio_sid is None
