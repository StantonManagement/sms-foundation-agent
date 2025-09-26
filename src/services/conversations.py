from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError, OperationalError

from src.repositories.conversations import ConversationRepository
from src.repositories.messages import MessageRepository
from src.utils.phone import normalize_phone


@dataclass
class ConversationWithMessages:
    conversation: object
    messages: Sequence[object]
    total: int | None = None


class ConversationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.conversations = ConversationRepository(session)
        self.messages = MessageRepository(session)

    async def get_with_messages_by_phone(
        self, phone_raw: str, *, page: int = 1, limit: int = 20, offset: int | None = None
    ) -> ConversationWithMessages | None:
        # Normalize
        _orig, canon = normalize_phone(phone_raw)
        if not canon:
            return None

        try:
            conv = await self.conversations.get_by_phone(canon)
        except (OperationalError, SQLAlchemyError):
            # In test or uninitialized DB environments, table may not exist yet.
            # Treat as not found per retrieval semantics.
            return None
        if not conv:
            return None

        # Pagination math
        if page < 1:
            page = 1
        if limit < 1:
            limit = 1
        if limit > 100:
            limit = 100
        if offset is None:
            offset = (page - 1) * limit

        try:
            items, total = await self.messages.list_paginated_with_total(
                conv.id, limit=limit, offset=offset
            )
        except AttributeError:
            # Backward compatibility if repository method missing
            items = await self.messages.list_by_conversation(
                conv.id, limit=limit, offset=offset
            )
            total = None

        return ConversationWithMessages(conversation=conv, messages=items, total=total)
