from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import SmsConversation


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_phone(self, phone_canon: str) -> Optional[SmsConversation]:
        stmt = select(SmsConversation).where(
            SmsConversation.phone_number_canonical == phone_canon
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def upsert_by_phone(
        self, *, original: str | None, canon: str
    ) -> SmsConversation:
        existing = await self.get_by_phone(canon)
        if existing:
            return existing
        entity = SmsConversation(
            phone_number_canonical=canon, phone_number_original=original
        )
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    async def update_language(self, id: int, lang: str, conf: float) -> None:
        stmt = (
            update(SmsConversation)
            .where(SmsConversation.id == id)
            .values(language_detected=lang, language_confidence=conf)
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def touch_last_message_at(self, id: int, ts: datetime) -> None:
        stmt = (
            update(SmsConversation)
            .where(SmsConversation.id == id)
            .values(last_message_at=ts)
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def set_tenant(self, id: int, tenant_id: str | None) -> None:
        """Set tenant_id for a conversation."""
        stmt = (
            update(SmsConversation)
            .where(SmsConversation.id == id)
            .values(tenant_id=tenant_id)
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def track_last_used_number(self, tenant_id: str, phone_canonical: str) -> None:
        """Associate tenant with this phone's conversation for 'last used' tracking.

        Current implementation sets tenant_id on the conversation identified by the
        canonical phone. Future enhancement may move to a dedicated mapping table.
        """
        stmt = (
            update(SmsConversation)
            .where(SmsConversation.phone_number_canonical == phone_canonical)
            .values(tenant_id=tenant_id)
        )
        await self.session.execute(stmt)
        await self.session.commit()
