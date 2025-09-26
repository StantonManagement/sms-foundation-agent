from __future__ import annotations

from typing import Mapping

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from src.repositories.messages import MessageRepository
from src.repositories.conversations import ConversationRepository
from src.services.language_detector import LanguageDetector
from src.utils.phone import normalize_phone, variants
from src.adapters.monitor_client import TenantLookupClient
from src.utils.config import get_settings


logger = structlog.get_logger(__name__)


class SmsInboundService:
    """Service to process inbound Twilio SMS webhooks idempotently by MessageSid."""

    async def handle_inbound(
        self,
        payload: Mapping[str, str],
        session: AsyncSession,
        *,
        request_id: str,
    ) -> dict[str, object]:
        sid = payload.get("MessageSid")
        if not sid:
            # Missing SID: log and no-op
            logger.warning(
                "inbound_sms_missing_sid",
                request_id=request_id,
                route="/webhook/twilio/sms",
            )
            return {"processed": False, "duplicate": False}

        msg_repo = MessageRepository(session)
        conv_repo = ConversationRepository(session)

        # First try a read to avoid insert where possible
        try:
            existing = await msg_repo.get_by_sid(sid)
        except SQLAlchemyError:
            logger.warning(
                "inbound_sms_db_unavailable",
                request_id=request_id,
                route="/webhook/twilio/sms",
                twilio_sid=sid,
            )
            return {"processed": False, "duplicate": False}
        if existing is not None:
            logger.info(
                "inbound_sms_processed",
                request_id=request_id,
                route="/webhook/twilio/sms",
                twilio_sid=sid,
                duplicate=True,
            )
            return {"processed": False, "duplicate": True}

        # Extract addressing and content
        from_number = payload.get("From")
        to_number = payload.get("To")
        body = payload.get("Body")

        # Normalize phone to canonical E.164; conversation is keyed by sender phone
        _orig, phone_canon = normalize_phone(from_number)
        conversation_id = None
        if phone_canon:
            # upsert conversation
            try:
                conv = await conv_repo.upsert_by_phone(original=from_number, canon=phone_canon)
                conversation_id = conv.id
            except SQLAlchemyError:
                logger.warning(
                    "inbound_sms_db_unavailable",
                    request_id=request_id,
                    route="/webhook/twilio/sms",
                    twilio_sid=sid,
                )
                return {"processed": False, "duplicate": False}

        # Attempt tenant lookup via Collections Monitor using phone variants
        if conversation_id is not None and from_number:
            settings = get_settings()
            v = variants(from_number)
            client = TenantLookupClient(settings.monitor_api_url)
            match = None
            try:
                match = await client.lookup(v)
            except Exception:
                # Errors in the client are swallowed; continue webhook path
                logger.warning(
                    "tenant_lookup_error",
                    request_id=request_id,
                    route="/webhook/twilio/sms",
                    twilio_sid=sid,
                    phone=from_number,
                )
            if match:
                try:
                    await conv_repo.set_tenant(conversation_id, match.tenant_id)
                    if phone_canon:
                        await conv_repo.track_last_used_number(match.tenant_id, phone_canon)
                    logger.info(
                        "tenant_lookup_outcome",
                        request_id=request_id,
                        route="/webhook/twilio/sms",
                        twilio_sid=sid,
                        phone=from_number,
                        monitor_outcome="found",
                        tenant_id=match.tenant_id,
                    )
                except SQLAlchemyError:
                    logger.warning(
                        "inbound_sms_db_unavailable",
                        request_id=request_id,
                        route="/webhook/twilio/sms",
                        twilio_sid=sid,
                    )
            else:
                logger.info(
                    "tenant_lookup_outcome",
                    request_id=request_id,
                    route="/webhook/twilio/sms",
                    twilio_sid=sid,
                    phone=from_number,
                    monitor_outcome="not_found",
                )

        # Insert full message with unique constraint guard for race-safety
        try:
            entity, created = await msg_repo.insert_inbound_full(
                conversation_id=conversation_id,
                sid=sid,
                from_number=from_number,
                to_number=to_number,
                content=body,
                raw_json=dict(payload),
            )
        except SQLAlchemyError:
            logger.warning(
                "inbound_sms_db_unavailable",
                request_id=request_id,
                route="/webhook/twilio/sms",
                twilio_sid=sid,
            )
            return {"processed": False, "duplicate": False}

        # Update conversation metadata if we created a message and have a conversation
        if created and conversation_id is not None:
            # Touch last_message_at
            try:
                await conv_repo.touch_last_message_at(conversation_id, entity.created_at)  # type: ignore[arg-type]
            except SQLAlchemyError:
                logger.warning(
                    "inbound_sms_db_unavailable",
                    request_id=request_id,
                    route="/webhook/twilio/sms",
                    twilio_sid=sid,
                )

            # Update language detection
            lang, conf = LanguageDetector.detect(body)
            try:
                await conv_repo.update_language(conversation_id, lang, float(conf))
            except SQLAlchemyError:
                logger.warning(
                    "inbound_sms_db_unavailable",
                    request_id=request_id,
                    route="/webhook/twilio/sms",
                    twilio_sid=sid,
                )
        logger.info(
            "inbound_sms_processed",
            request_id=request_id,
            route="/webhook/twilio/sms",
            twilio_sid=sid,
            duplicate=not created,
            phone=from_number,
        )
        return {"processed": created, "duplicate": not created, "id": getattr(entity, "id", None)}
