from __future__ import annotations

import hashlib
import json
from typing import Mapping, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import SmsMessageStatusEvent


def _compute_event_hash(status: str, error_code: str | None, payload: Mapping[str, str]) -> str:
    """Compute a stable short hash for idempotent event storage."""
    h = hashlib.sha256()
    h.update(status.encode("utf-8"))
    if error_code:
        h.update(str(error_code).encode("utf-8"))
    # Include stable JSON of payload
    try:
        h.update(json.dumps(dict(payload), sort_keys=True).encode("utf-8"))
    except Exception:
        # Best-effort: ensure function is total
        h.update(repr(payload).encode("utf-8"))
    return h.hexdigest()[:64]


class StatusEventRepository:
    """Repository for sms_message_status_events with idempotent append semantics."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def append(
        self,
        *,
        message_id: int,
        status: str,
        error_code: Optional[str],
        payload: Mapping[str, str] | None,
    ) -> tuple[SmsMessageStatusEvent | None, bool]:
        """Insert event row if not already recorded; returns (entity, created)."""
        raw = dict(payload) if payload is not None else None
        event_hash = _compute_event_hash(status, error_code, raw or {})

        entity = SmsMessageStatusEvent(
            message_id=message_id,
            event_status=status,
            error_code=error_code,
            event_hash=event_hash,
            raw_webhook_data=raw,
        )
        self.session.add(entity)
        try:
            await self.session.commit()
            await self.session.refresh(entity)
            return entity, True
        except IntegrityError:
            await self.session.rollback()
            # Already inserted; load existing row for convenience
            try:
                stmt = select(SmsMessageStatusEvent).where(
                    SmsMessageStatusEvent.message_id == message_id,
                    SmsMessageStatusEvent.event_hash == event_hash,
                )
                res = await self.session.execute(stmt)
                existing = res.scalar_one_or_none()
                return existing, False
            except SQLAlchemyError:
                return None, False
        except SQLAlchemyError:
            await self.session.rollback()
            raise

    async def count_for_message(self, message_id: int) -> int:
        stmt = select(SmsMessageStatusEvent).where(
            SmsMessageStatusEvent.message_id == message_id
        )
        res = await self.session.execute(stmt)
        return len(list(res.scalars().all()))

