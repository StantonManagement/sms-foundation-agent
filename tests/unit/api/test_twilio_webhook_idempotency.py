from __future__ import annotations

from typing import AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.api.webhooks.twilio import _compute_twilio_signature
from src.api.webhooks import twilio as twilio_mod
from src.db.models import Base, SmsMessage
from src.main import app
from src.utils.config import Settings, get_settings


@pytest.fixture(scope="module")
def test_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    return engine


@pytest.fixture(scope="module", autouse=True)
def prepare_schema(test_engine):
    import anyio

    async def _create():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    anyio.run(_create)


@pytest.fixture(scope="module")
def session_maker(test_engine):
    return async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def override_dependencies(session_maker):
    # Force signature token via settings override
    app.dependency_overrides[get_settings] = lambda: Settings(TWILIO_AUTH_TOKEN="test_token")
    # Route uses a module-level provider; override to use our in-memory session maker
    original_provider = twilio_mod.session_maker_provider
    twilio_mod.session_maker_provider = lambda: session_maker
    yield
    app.dependency_overrides.clear()
    twilio_mod.session_maker_provider = original_provider


def test_twilio_webhook_duplicate_posts_yield_single_row(session_maker):
    client = TestClient(app)
    url = "http://testserver/webhook/twilio/sms"

    payload = {
        "MessageSid": "SM999",
        "From": "+15555550100",
        "To": "+15555550101",
        "Body": "Hello",
    }
    sig = _compute_twilio_signature(url, payload, "test_token")
    headers = {"X-Twilio-Signature": sig}

    # First post
    res1 = client.post("/webhook/twilio/sms", data=payload, headers=headers)
    assert res1.status_code == 200

    # Second post (duplicate)
    res2 = client.post("/webhook/twilio/sms", data=payload, headers=headers)
    assert res2.status_code == 200

    # Verify single row in DB using a new session
    async def _count_rows() -> int:
        async with session_maker() as session:  # type: ignore[misc]
            result = await session.execute(select(func.count(SmsMessage.id)))
            (count,) = result.one()
            return int(count)

    import anyio
    count = anyio.run(_count_rows)

    assert count == 1
