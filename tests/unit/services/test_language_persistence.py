import pytest
import respx
from httpx import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.models import Base, SmsConversation
from src.services.sms_inbound import SmsInboundService


@pytest.mark.asyncio
@respx.mock
async def test_language_updates_and_profile_calls(monkeypatch):
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

    monitor_base = "https://monitor.example.com"
    profile_base = "https://tenant.example.com"
    monkeypatch.setenv("MONITOR_API_URL", monitor_base)
    monkeypatch.setenv("TENANT_PROFILE_API_URL", profile_base)
    cfg.get_settings.cache_clear()  # type: ignore[attr-defined]

    # Mock monitor API: same tenant for this number
    respx.get(f"{monitor_base}/tenants/lookup").mock(
        return_value=Response(200, json={"tenant_id": "tenant-42"})
    )
    # Mock profile API: count calls
    route = respx.put(f"{profile_base}/tenants/tenant-42/language").mock(
        return_value=Response(204)
    )

    async with session_maker() as session:
        service = SmsInboundService()

        # First inbound English
        payload1 = {"MessageSid": "SM-L1", "From": "+14155551212", "Body": "hello"}
        await service.handle_inbound(payload1, session, request_id="r1")
        conv = await session.execute(
            select(SmsConversation).where(
                SmsConversation.phone_number_canonical == "+14155551212"
            )
        )
        conv = conv.scalar_one()
        assert conv.language_detected == "en"
        assert conv.language_confidence >= 0.7

        # Second inbound Spanish with higher confidence
        payload2 = {"MessageSid": "SM-L2", "From": "+14155551212", "Body": "sí"}
        await service.handle_inbound(payload2, session, request_id="r2")
        conv = await session.execute(
            select(SmsConversation).where(
                SmsConversation.phone_number_canonical == "+14155551212"
            )
        )
        conv = conv.scalar_one()
        assert conv.language_detected == "es"
        assert conv.language_confidence >= 0.8

        # Third inbound unknown should not override stronger value
        payload3 = {"MessageSid": "SM-L3", "From": "+14155551212", "Body": "12345"}
        await service.handle_inbound(payload3, session, request_id="r3")
        conv = await session.execute(
            select(SmsConversation).where(
                SmsConversation.phone_number_canonical == "+14155551212"
            )
        )
        conv = conv.scalar_one()
        assert conv.language_detected == "es"  # unchanged

    # Ensure profile update attempted at least twice (first EN, then ES)
    assert route.called
    assert route.call_count >= 2


@pytest.mark.asyncio
@respx.mock
async def test_persist_across_conversations_reuse_last_known(monkeypatch):
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

    from src.utils import config as cfg

    monitor_base = "https://monitor.example.com"
    profile_base = "https://tenant.example.com"
    monkeypatch.setenv("MONITOR_API_URL", monitor_base)
    monkeypatch.setenv("TENANT_PROFILE_API_URL", profile_base)
    cfg.get_settings.cache_clear()  # type: ignore[attr-defined]

    # Mock monitor: map two numbers to same tenant
    def monitor_response(request):
        return Response(200, json={"tenant_id": "tenant-88"})

    respx.get(f"{monitor_base}/tenants/lookup").mock(side_effect=monitor_response)
    # Mock profile API
    respx.put(f"{profile_base}/tenants/tenant-88/language").mock(return_value=Response(204))

    async with session_maker() as session:
        service = SmsInboundService()

        # First conversation establishes ES
        await service.handle_inbound(
            {"MessageSid": "SM-A1", "From": "+14150000001", "Body": "hola"},
            session,
            request_id="rA1",
        )
        conv1 = await session.execute(
            select(SmsConversation).where(
                SmsConversation.phone_number_canonical == "+14150000001"
            )
        )
        conv1 = conv1.scalar_one()
        assert conv1.language_detected == "es"

        # Second conversation for same tenant with unknown signal should reuse ES
        await service.handle_inbound(
            {"MessageSid": "SM-A2", "From": "+14150000002", "Body": "???"},
            session,
            request_id="rA2",
        )
        conv2 = await session.execute(
            select(SmsConversation).where(
                SmsConversation.phone_number_canonical == "+14150000002"
            )
        )
        conv2 = conv2.scalar_one()
        assert conv2.language_detected == "es"  # reused from tenant last-known

