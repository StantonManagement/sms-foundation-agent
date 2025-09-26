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
async def test_inbound_sets_tenant_when_found(monkeypatch):
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

    # Mock monitor API
    respx.get(f"{base}/tenants/lookup").mock(
        return_value=Response(200, json={"tenant_id": "tenant-42"})
    )

    async with session_maker() as session:
        service = SmsInboundService()
        payload = {"MessageSid": "SMtid1", "From": "+14155551212", "Body": "hello"}
        await service.handle_inbound(payload, session, request_id="r1")

        # Verify conversation has tenant_id set
        conv = await session.execute(
            select(SmsConversation).where(
                SmsConversation.phone_number_canonical == "+14155551212"
            )
        )
        conv = conv.scalar_one()
        assert conv.tenant_id == "tenant-42"


@pytest.mark.asyncio
@respx.mock
async def test_inbound_no_match_leaves_null(monkeypatch):
    # DB
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

    base = "https://monitor.example.com"
    monkeypatch.setenv("MONITOR_API_URL", base)
    cfg.get_settings.cache_clear()  # type: ignore[attr-defined]

    respx.get(f"{base}/tenants/lookup").mock(return_value=Response(404))

    async with session_maker() as session:
        service = SmsInboundService()
        payload = {"MessageSid": "SMtid2", "From": "+14155559999", "Body": "hola"}
        await service.handle_inbound(payload, session, request_id="r2")

        conv = await session.execute(
            select(SmsConversation).where(
                SmsConversation.phone_number_canonical == "+14155559999"
            )
        )
        conv = conv.scalar_one()
        assert conv.tenant_id is None

