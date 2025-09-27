from __future__ import annotations

from datetime import datetime
from typing import Mapping

import structlog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.messages import MessageRepository
from src.repositories.conversations import ConversationRepository
from src.repositories.status_events import StatusEventRepository


logger = structlog.get_logger(__name__)


_TERMINAL_STATUSES = {"delivered", "failed", "undelivered"}


def _normalize_status(value: str | None) -> str:
    if not value:
        return "unknown"
    v = value.lower().strip()
    mapping = {
        "queued": "queued",
        "sending": "sending",
        "sent": "sent",
        "delivered": "delivered",
        "undelivered": "undelivered",
        "failed": "failed",
        "receiving": "receiving",
        "received": "received",
    }
    return mapping.get(v, "unknown")


class StatusService:
    """Process Twilio delivery status callbacks idempotently."""

    async def process_status(
        self,
        payload: Mapping[str, str],
        session: AsyncSession,
        *,
        request_id: str,
    ) -> dict[str, object]:
        sid = payload.get("MessageSid")
        status_raw = payload.get("MessageStatus")
        new_status = _normalize_status(status_raw)
        error_code = payload.get("ErrorCode")

        if not sid:
            logger.warning(
                "status_missing_sid",
                request_id=request_id,
                route="/webhook/twilio/status",
            )
            return {"processed": False, "duplicate": False}

        msg_repo = MessageRepository(session)
        conv_repo = ConversationRepository(session)
        event_repo = StatusEventRepository(session)

        try:
            msg = await msg_repo.get_by_sid(sid)
        except SQLAlchemyError:
            logger.warning(
                "status_db_unavailable",
                request_id=request_id,
                route="/webhook/twilio/status",
                twilio_sid=sid,
            )
            return {"processed": False, "duplicate": False}

        if not msg:
            logger.info(
                "status_unknown_message_sid",
                request_id=request_id,
                route="/webhook/twilio/status",
                twilio_sid=sid,
            )
            return {"processed": False, "duplicate": False}

        prev_status = (msg.delivery_status or "unknown").lower()
        conv_id = msg.conversation_id

        # Record event history idempotently first
        try:
            await event_repo.append(
                message_id=msg.id,
                status=new_status,
                error_code=error_code,
                payload=payload,
            )
        except SQLAlchemyError:
            # Swallow event storage errors to keep webhook resilient
            logger.warning(
                "status_event_persist_error",
                request_id=request_id,
                route="/webhook/twilio/status",
                twilio_sid=sid,
            )

        # Determine if this is a duplicate/no-op transition
        duplicate = prev_status == new_status or new_status == "unknown"
        should_update = False
        if not duplicate:
            # Only update if previous is non-terminal or new is terminal and previous not terminal
            if prev_status in _TERMINAL_STATUSES:
                should_update = False
            else:
                should_update = True

        if should_update:
            try:
                await msg_repo.update_status(msg.id, new_status)
                # Update in-memory for subsequent logic
                msg.delivery_status = new_status
            except SQLAlchemyError:
                logger.warning(
                    "status_db_unavailable",
                    request_id=request_id,
                    route="/webhook/twilio/status",
                    twilio_sid=sid,
                )
                return {"processed": False, "duplicate": False}

        # Touch conversation last_message_at for delivered events
        if new_status == "delivered" and conv_id is not None:
            try:
                await conv_repo.touch_last_message_at(conv_id, datetime.utcnow())
            except SQLAlchemyError:
                logger.warning(
                    "status_db_unavailable",
                    request_id=request_id,
                    route="/webhook/twilio/status",
                    twilio_sid=sid,
                )

        logger.info(
            "status_processed",
            request_id=request_id,
            route="/webhook/twilio/status",
            twilio_sid=sid,
            previous_status=prev_status,
            new_status=new_status,
            duplicate=duplicate and not should_update,
        )

        return {"processed": should_update, "duplicate": duplicate and not should_update}
