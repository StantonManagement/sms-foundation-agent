import pytest
import respx
from httpx import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.models import Base, SmsConversation, SmsMessage
from src.services.sms_inbound import SmsInboundService


@pytest.mark.asyncio
@respx.mock
async def test_unknown_then_known_updates_same_conversation(monkeypatch):
    # DB setup
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

    # Settings
    from src.utils import config as cfg

    base = "https://monitor.example.com"
    monkeypatch.setenv("MONITOR_API_URL", base)
    cfg.get_settings.cache_clear()  # type: ignore[attr-defined]

    # Mock monitor API: first no match, then match
    calls = {"n": 0}

    def lookup_handler(request):
        # First webhook will try several variants; ensure all return 404
        calls["n"] += 1
        if calls["n"] <= 4:
            return Response(404)
        return Response(200, json={"tenant_id": "tenant-99"})

    respx.get(f"{base}/tenants/lookup").mock(side_effect=lookup_handler)

    async with session_maker() as session:
        service = SmsInboundService()
        phone = "+14155558888"

        # First inbound: unknown
        await service.handle_inbound(
            {"MessageSid": "SM-R1", "From": phone, "Body": "hi"},
            session,
            request_id="r1",
        )

        conv = await session.execute(
            select(SmsConversation).where(SmsConversation.phone_number_canonical == phone)
        )
        conv = conv.scalar_one()
        assert conv.tenant_id is None

        # Second inbound: becomes known
        await service.handle_inbound(
            {"MessageSid": "SM-R2", "From": phone, "Body": "hola"},
            session,
            request_id="r2",
        )

        conv2 = await session.execute(
            select(SmsConversation).where(SmsConversation.phone_number_canonical == phone)
        )
        conv2 = conv2.scalar_one()
        assert conv2.id == conv.id  # same conversation
        assert conv2.tenant_id == "tenant-99"  # reconciled

        # No duplicate messages for same SID; total messages should be 2 (R1, R2)
        count = await session.execute(
            select(func.count()).select_from(
                select(SmsMessage.id)
                .where(SmsMessage.conversation_id == conv.id)
                .subquery()
            )
        )
        assert int(count.scalar() or 0) == 2

    # Ensure our handler was invoked twice
    assert calls["n"] >= 5  # multiple attempts across two webhooks
