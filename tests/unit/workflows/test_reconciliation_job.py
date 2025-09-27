import pytest
import respx
from httpx import Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.models import Base, SmsConversation
from src.workflows.reconciliation import reconcile_unknown_conversations


@pytest.mark.asyncio
@respx.mock
async def test_reconciles_unknown_conversations_idempotently(monkeypatch):
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

    # Insert an unknown conversation
    async with session_maker() as session:
        c = SmsConversation(
            phone_number_canonical="+14157770000",
            phone_number_original="(415) 777-0000",
        )
        session.add(c)
        await session.commit()

    # Settings
    from src.utils import config as cfg

    base = "https://monitor.example.com"
    monkeypatch.setenv("MONITOR_API_URL", base)
    cfg.get_settings.cache_clear()  # type: ignore[attr-defined]

    # Mock monitor API: always return tenant
    respx.get(f"{base}/tenants/lookup").mock(
        return_value=Response(200, json={"tenant_id": "tenant-123"})
    )

    # First run should reconcile 1 item
    summary1 = await reconcile_unknown_conversations(session_maker, batch_size=10)
    assert summary1["processed"] == 1
    assert summary1["succeeded"] == 1
    assert summary1["no_match"] == 0

    # Second run should be a no-op (nothing unknown left)
    summary2 = await reconcile_unknown_conversations(session_maker, batch_size=10)
    assert summary2["processed"] == 0
    assert summary2["succeeded"] == 0
    assert summary2["no_match"] == 0

