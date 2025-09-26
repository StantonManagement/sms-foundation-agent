import pytest

from src.services.conversations import ConversationService


@pytest.mark.asyncio
async def test_service_normalizes_and_not_found(async_session):
    svc = ConversationService(async_session)
    res = await svc.get_with_messages_by_phone("(415) 555-0000")
    assert res is None

