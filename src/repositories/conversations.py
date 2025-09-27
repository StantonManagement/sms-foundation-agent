from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
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
        """Backward-compatible get-or-create by phone.

        If a concurrent insert occurs, silently return the existing row.
        """
        existing = await self.get_by_phone(canon)
        if existing:
            return existing
        entity = SmsConversation(
            phone_number_canonical=canon, phone_number_original=original
        )
        self.session.add(entity)
        try:
            await self.session.commit()
            await self.session.refresh(entity)
            return entity
        except IntegrityError:
            await self.session.rollback()
            existing = await self.get_by_phone(canon)
            if not existing:
                raise
            return existing

    async def upsert_by_phone_returning_created(
        self, *, original: str | None, canon: str
    ) -> tuple[SmsConversation, bool]:
        """Get or create a conversation and also return created flag.

        Handles races via unique constraint: if a concurrent insert wins, reload and
        return (existing, False).
        """
        existing = await self.get_by_phone(canon)
        if existing:
            return existing, False
        entity = SmsConversation(
            phone_number_canonical=canon, phone_number_original=original
        )
        self.session.add(entity)
        try:
            await self.session.commit()
            await self.session.refresh(entity)
            return entity, True
        except IntegrityError:
            await self.session.rollback()
            existing = await self.get_by_phone(canon)
            if not existing:
                raise
            return existing, False

    async def get_by_id(self, id: int) -> Optional[SmsConversation]:
        stmt = select(SmsConversation).where(SmsConversation.id == id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

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

    async def find_last_known_language(self, tenant_id: str) -> tuple[str, float] | None:
        """Return the most recent known language for a tenant.

        Prefers most recently updated conversation with a non-unknown language.
        """
        stmt = (
            select(SmsConversation.language_detected, SmsConversation.language_confidence)
            .where(
                SmsConversation.tenant_id == tenant_id,
                SmsConversation.language_detected != "unknown",
            )
            .order_by(SmsConversation.updated_at.desc())
            .limit(1)
        )
        res = await self.session.execute(stmt)
        row = res.first()
        if not row:
            return None
        lang, conf = row
        return str(lang), float(conf)

    async def list_unknown(self, *, limit: int = 100, offset: int = 0) -> list[SmsConversation]:
        """Return conversations without a tenant assigned.

        Ordered by most recent activity first, then created_at.
        """
        stmt = (
            select(SmsConversation)
            .where(SmsConversation.tenant_id.is_(None))
            .order_by(SmsConversation.last_message_at.desc().nullslast(), SmsConversation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
