from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import SmsMessage


class MessageRepository:
    """Repository for sms_messages table."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_sid(self, sid: str) -> Optional[SmsMessage]:
        stmt = select(SmsMessage).where(SmsMessage.twilio_sid == sid)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def insert_inbound_minimal(self, sid: str) -> tuple[SmsMessage | None, bool]:
        """Insert a minimal inbound message row.

        Returns: (entity, created)
        created=False indicates duplicate/no-op.
        """
        entity = SmsMessage(twilio_sid=sid, direction="inbound")
        self.session.add(entity)
        try:
            await self.session.commit()
            await self.session.refresh(entity)
            return entity, True
        except IntegrityError:
            # Unique constraint violation -> treat as duplicate; rollback transaction
            await self.session.rollback()
            return None, False
        except SQLAlchemyError:
            await self.session.rollback()
            raise

    async def insert_inbound_full(
        self,
        *,
        conversation_id: int | None,
        sid: str,
        from_number: str | None,
        to_number: str | None,
        content: str | None,
        raw_json: dict | None,
    ) -> tuple[SmsMessage | None, bool]:
        entity = SmsMessage(
            conversation_id=conversation_id,
            twilio_sid=sid,
            direction="inbound",
            from_number=from_number,
            to_number=to_number,
            message_content=content,
            raw_webhook_data=raw_json,
        )
        self.session.add(entity)
        try:
            await self.session.commit()
            await self.session.refresh(entity)
            return entity, True
        except IntegrityError:
            await self.session.rollback()
            return None, False
        except SQLAlchemyError:
            await self.session.rollback()
            raise

    async def list_by_conversation(
        self, conversation_id: int, *, limit: int = 20, offset: int = 0
    ) -> Sequence[SmsMessage]:
        stmt = (
            select(SmsMessage)
            .where(SmsMessage.conversation_id == conversation_id)
            .order_by(SmsMessage.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        # scalars().all() returns list[SmsMessage]
        return list(res.scalars().all())
