from __future__ import annotations

import anyio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.main import app
from src.db.models import Base, SmsMessage
from src.api.sms import get_twilio_client
from src.adapters.twilio_client import TwilioClient, TwilioError


class _FakeTwilio(TwilioClient):
    def __init__(self, sid: str | None = "SM-TEST", should_fail: bool = False):  # type: ignore[no-untyped-def]
        self._sid = sid
        self._fail = should_fail

    async def send_sms(self, to: str, body: str, *, from_number: str | None = None) -> str:  # type: ignore[override]
        if self._fail:
            raise TwilioError("boom")
        return self._sid or "SM-TEST"


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
    async def _create():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    anyio.run(_create)


@pytest.fixture(scope="module")
def session_maker(test_engine):
    return async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def override_deps(session_maker):
    # DB dependency
    async def _dep():
        async with session_maker() as session:  # type: ignore[misc]
            yield session

    from src.db import base as db_base

    app.dependency_overrides[db_base.get_session] = _dep
    # Twilio dependency defaults to success
    app.dependency_overrides[get_twilio_client] = lambda: _FakeTwilio("SM-OK")
    yield
    app.dependency_overrides.clear()


def test_send_validation_empty_body():
    client = TestClient(app)
    res = client.post("/sms/send", json={"to": "+15555550123", "body": "   "})
    assert res.status_code == 400


def test_send_validation_bad_phone():
    client = TestClient(app)
    res = client.post("/sms/send", json={"to": "123", "body": "hello"})
    assert res.status_code == 400


def test_send_happy_path_creates_and_updates(session_maker):
    client = TestClient(app)
    res = client.post("/sms/send", json={"to": "+1 (555) 555-0199", "body": "Hello there"})
    assert res.status_code == 202
    data = res.json()
    assert "id" in data and data["id"]
    assert data["twilio_sid"] == "SM-OK"
    # Inspect DB
    async def _check():
        async with session_maker() as session:  # type: ignore[misc]
            stmt = select(SmsMessage).order_by(SmsMessage.id.desc()).limit(1)
            res = await session.execute(stmt)
            msg = res.scalar_one()
            assert msg.direction == "outbound"
            assert msg.to_number.startswith("+")
            assert msg.message_content == "Hello there"
            assert msg.twilio_sid == "SM-OK"
            assert msg.delivery_status in ("queued", "sent", "queued")

    anyio.run(_check)


def test_send_provider_error_sets_failed_and_returns_502(session_maker):
    # Override Twilio to fail
    app.dependency_overrides[get_twilio_client] = lambda: _FakeTwilio(should_fail=True)
    client = TestClient(app)
    res = client.post("/sms/send", json={"to": "+15555550155", "body": "Hello"})
    assert res.status_code == 502

    async def _check():
        async with session_maker() as session:  # type: ignore[misc]
            stmt = select(SmsMessage).order_by(SmsMessage.id.desc()).limit(1)
            res = await session.execute(stmt)
            msg = res.scalar_one()
            assert msg.direction == "outbound"
            assert msg.delivery_status == "failed"
            assert msg.twilio_sid is None

    anyio.run(_check)

