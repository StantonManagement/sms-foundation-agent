from __future__ import annotations

import anyio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.main import app
from src.db.models import Base, SmsConversation, SmsMessage, SmsMessageStatusEvent
from src.api.webhooks.twilio import _compute_twilio_signature
from src.utils.config import get_settings


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
def override_session_provider(session_maker):
    # Monkeypatch the webhook module's session maker provider
    import src.api.webhooks.twilio as tw

    tw.session_maker_provider = lambda: session_maker  # type: ignore[assignment]
    yield
    # no cleanup needed; tests run in isolated engine


def _signed_headers(url: str, payload: dict[str, str]) -> dict[str, str]:
    # Use actual auth token from settings to match app verification
    token = get_settings().twilio_auth_token
    sig = _compute_twilio_signature(url, payload, token)
    return {"X-Twilio-Signature": sig}


def test_status_webhook_updates_and_idempotent(session_maker):
    client = TestClient(app)

    # Seed a conversation and outbound message with a SID
    async def _seed():
        async with session_maker() as session:  # type: ignore[misc]
            conv = SmsConversation(phone_number_canonical="+15555550123")
            session.add(conv)
            await session.commit()
            await session.refresh(conv)
            msg = SmsMessage(
                conversation_id=conv.id,
                direction="outbound",
                to_number="+15555550123",
                message_content="Hello",
                delivery_status="sent",
                twilio_sid="SM-ABC",
            )
            session.add(msg)
            await session.commit()
            await session.refresh(msg)
            return conv.id, msg.id

    conv_id, message_id = anyio.run(_seed)

    # First callback: delivered
    url = "http://testserver/webhook/twilio/status"
    form = {"MessageSid": "SM-ABC", "MessageStatus": "delivered"}
    res = client.post(url, data=form, headers=_signed_headers(url, form))
    assert res.status_code == 200

    async def _check_once():
        async with session_maker() as session:  # type: ignore[misc]
            m = (await session.execute(select(SmsMessage).where(SmsMessage.id == message_id))).scalar_one()
            assert m.delivery_status == "delivered"
            c = (
                await session.execute(select(SmsConversation).where(SmsConversation.id == conv_id))
            ).scalar_one()
            assert c.last_message_at is not None
            # One status event stored
            rows = (
                await session.execute(
                    select(SmsMessageStatusEvent).where(SmsMessageStatusEvent.message_id == message_id)
                )
            ).scalars().all()
            assert len(rows) == 1

    anyio.run(_check_once)

    # Duplicate callback: no change, no new event
    res2 = client.post(url, data=form, headers=_signed_headers(url, form))
    assert res2.status_code == 200

    async def _check_dupe():
        async with session_maker() as session:  # type: ignore[misc]
            events = (
                await session.execute(
                    select(SmsMessageStatusEvent).where(SmsMessageStatusEvent.message_id == message_id)
                )
            ).scalars().all()
            assert len(events) == 1

    anyio.run(_check_dupe)


def test_status_webhook_invalid_signature_forbidden():
    client = TestClient(app)
    url = "http://testserver/webhook/twilio/status"
    res = client.post(url, data={"MessageSid": "SM-X", "MessageStatus": "queued"}, headers={"X-Twilio-Signature": "bogus"})
    assert res.status_code == 403
