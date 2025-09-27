from __future__ import annotations

import anyio
import pytest
from sqlalchemy import select

from src.db.models import SmsConversation, SmsMessage, SmsMessageStatusEvent
from src.services.status_service import StatusService


@pytest.mark.asyncio
async def test_status_progression_and_events(async_session):
    session = async_session

    # Create conversation and outbound message with SID
    conv = SmsConversation(phone_number_canonical="+15555550150")
    session.add(conv)
    await session.commit()
    await session.refresh(conv)

    msg = SmsMessage(
        conversation_id=conv.id,
        direction="outbound",
        to_number="+15555550150",
        message_content="Hello",
        delivery_status=None,
        twilio_sid="SM-XYZ",
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    mid = msg.id

    svc = StatusService()
    # queued
    await svc.process_status({"MessageSid": "SM-XYZ", "MessageStatus": "queued"}, session, request_id="r1")
    await session.refresh(msg)
    assert msg.delivery_status == "queued"
    # sent
    await svc.process_status({"MessageSid": "SM-XYZ", "MessageStatus": "sent"}, session, request_id="r2")
    await session.refresh(msg)
    assert msg.delivery_status == "sent"
    # delivered
    await svc.process_status({"MessageSid": "SM-XYZ", "MessageStatus": "delivered"}, session, request_id="r3")
    await session.refresh(msg)
    assert msg.delivery_status == "delivered"

    # last_message_at touched on delivered
    await session.refresh(conv)
    assert conv.last_message_at is not None

    # Duplicate delivered does not create another event
    await svc.process_status({"MessageSid": "SM-XYZ", "MessageStatus": "delivered"}, session, request_id="r4")
    rows = (
        await session.execute(
            select(SmsMessageStatusEvent).where(SmsMessageStatusEvent.message_id == mid)
        )
    ).scalars().all()
    # Expect 3 events (queued, sent, delivered), not 4
    assert len(rows) == 3


@pytest.mark.asyncio
async def test_failed_and_undelivered_paths(async_session):
    session = async_session

    # Start at sent
    conv = SmsConversation(phone_number_canonical="+15555550999")
    session.add(conv)
    await session.commit()
    await session.refresh(conv)

    msg = SmsMessage(
        conversation_id=conv.id,
        direction="outbound",
        to_number="+15555550999",
        message_content="Hi",
        delivery_status="sent",
        twilio_sid="SM-ERR",
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)

    svc = StatusService()
    # undelivered should override sent
    await svc.process_status({"MessageSid": "SM-ERR", "MessageStatus": "undelivered", "ErrorCode": "30005"}, session, request_id="x1")
    await session.refresh(msg)
    assert msg.delivery_status == "undelivered"

    # subsequent failed should be ignored (terminal -> terminal)
    await svc.process_status({"MessageSid": "SM-ERR", "MessageStatus": "failed", "ErrorCode": "30006"}, session, request_id="x2")
    await session.refresh(msg)
    assert msg.delivery_status == "undelivered"
