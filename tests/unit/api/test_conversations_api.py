from __future__ import annotations

from datetime import datetime

import anyio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.api.conversations import get_conversation
from src.db.models import Base, SmsMessage
from src.main import app
from src.repositories.conversations import ConversationRepository
from src.repositories.messages import MessageRepository


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
def override_db_dependency(session_maker):
    # Replace the get_session dependency used by the conversations router
    async def _dep():
        async with session_maker() as session:  # type: ignore[misc]
            yield session

    from src.db import base as db_base

    original = db_base.get_session
    app.dependency_overrides[db_base.get_session] = _dep
    yield
    app.dependency_overrides.clear()


def test_get_conversation_not_found():
    client = TestClient(app)
    res = client.get("/conversations/+19999999999")
    assert res.status_code == 404


def test_get_conversation_found_with_normalization(session_maker):
    client = TestClient(app)

    async def _setup():
        async with session_maker() as session:  # type: ignore[misc]
            conv_repo = ConversationRepository(session)
            msg_repo = MessageRepository(session)
            # Upsert conversation by canonical phone
            conv = await conv_repo.upsert_by_phone(original="(555) 555-0100", canon="+15555550100")
            # Insert one message
            await msg_repo.insert_inbound_full(
                conversation_id=conv.id,
                sid="SM-A",
                from_number="(555) 555-0100",
                to_number="+15555550101",
                content="hello",
                raw_json={"MessageSid": "SM-A"},
            )

    anyio.run(_setup)

    # Call with a non-E.164 form to verify normalization works
    res = client.get("/conversations/5555550100")
    assert res.status_code == 200
    body = res.json()
    assert body["phone_number_canonical"] == "+15555550100"
    assert len(body["messages"]) == 1
    # Contract: include content (alias of message_content), and pagination echoes
    assert body["messages"][0]["content"] == "hello"
    assert body["page"] == 1
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert body["total"] == 1


def test_get_conversation_ordering_and_pagination(session_maker):
    client = TestClient(app)

    async def _setup_and_query():
        async with session_maker() as session:  # type: ignore[misc]
            conv_repo = ConversationRepository(session)
            msg_repo = MessageRepository(session)
            conv = await conv_repo.upsert_by_phone(original="+1 555 555 0200", canon="+15555550200")
            # Insert three messages
            e1, _ = await msg_repo.insert_inbound_full(
                conversation_id=conv.id,
                sid="SM-1",
                from_number="+15555550200",
                to_number="+15555550201",
                content="m1",
                raw_json={"MessageSid": "SM-1"},
            )
            e2, _ = await msg_repo.insert_inbound_full(
                conversation_id=conv.id,
                sid="SM-2",
                from_number="+15555550200",
                to_number="+15555550201",
                content="m2",
                raw_json={"MessageSid": "SM-2"},
            )
            e3, _ = await msg_repo.insert_inbound_full(
                conversation_id=conv.id,
                sid="SM-3",
                from_number="+15555550200",
                to_number="+15555550201",
                content="m3",
                raw_json={"MessageSid": "SM-3"},
            )

            # Make created_at deterministic: e1 older, e3 newest
            await session.execute(
                update(SmsMessage)
                .where(SmsMessage.id == e1.id)
                .values(created_at=datetime.fromisoformat("2024-01-01T12:00:00"))
            )
            await session.execute(
                update(SmsMessage)
                .where(SmsMessage.id == e2.id)
                .values(created_at=datetime.fromisoformat("2024-01-01T12:00:01"))
            )
            await session.execute(
                update(SmsMessage)
                .where(SmsMessage.id == e3.id)
                .values(created_at=datetime.fromisoformat("2024-01-01T12:00:02"))
            )
            await session.commit()

        # Query ordering desc default limit
        res1 = client.get("/conversations/+15555550200")
        assert res1.status_code == 200
        body1 = res1.json()
        msgs = body1["messages"]
        assert [m["message_content"] for m in msgs] == ["m3", "m2", "m1"]
        assert body1["total"] == 3
        assert body1["page"] == 1 and body1["limit"] == 20 and body1["offset"] == 0

        # Pagination: limit 2
        res2 = client.get("/conversations/+15555550200?limit=2")
        assert res2.status_code == 200
        body2 = res2.json()
        msgs2 = body2["messages"]
        assert [m["message_content"] for m in msgs2] == ["m3", "m2"]
        assert body2["total"] == 3
        assert body2["page"] == 1 and body2["limit"] == 2 and body2["offset"] == 0

        # Pagination with offset 1
        res3 = client.get("/conversations/+15555550200?limit=2&offset=1")
        assert res3.status_code == 200
        body3 = res3.json()
        msgs3 = body3["messages"]
        assert [m["message_content"] for m in msgs3] == ["m2", "m1"]
        assert body3["total"] == 3
        assert body3["page"] == 1 and body3["limit"] == 2 and body3["offset"] == 1


def test_get_conversation_empty_messages(session_maker):
    client = TestClient(app)

    async def _setup():
        async with session_maker() as session:  # type: ignore[misc]
            conv_repo = ConversationRepository(session)
            await conv_repo.upsert_by_phone(original="+1 555 555 0300", canon="+15555550300")

    anyio.run(_setup)

    res = client.get("/conversations/+15555550300")
    assert res.status_code == 200
    body = res.json()
    assert body["messages"] == []
    assert body["total"] == 0
