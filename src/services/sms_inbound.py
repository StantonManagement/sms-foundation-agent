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
from src.adapters.metrics import Metrics
from src.adapters.tenant_profile_client import TenantProfileClient
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
        conv_created = False
        if phone_canon:
            # upsert conversation
            try:
                conv, created = await conv_repo.upsert_by_phone_returning_created(
                    original=from_number, canon=phone_canon
                )
                conversation_id = conv.id
                conv_created = bool(created)
            except SQLAlchemyError:
                logger.warning(
                    "inbound_sms_db_unavailable",
                    request_id=request_id,
                    route="/webhook/twilio/sms",
                    twilio_sid=sid,
                )
                return {"processed": False, "duplicate": False}

        # Attempt tenant lookup via Collections Monitor using phone variants
        monitor_match = None
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
                    monitor_match = match
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
                monitor_match = None

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

            # Language detection and conflict resolution
            detected_lang, detected_conf = LanguageDetector.detect(body)
            prev_lang = "unknown"
            prev_conf = 0.0
            tenant_id: str | None = None
            try:
                current = await conv_repo.get_by_id(conversation_id)
                if current:
                    prev_lang = current.language_detected or "unknown"
                    prev_conf = float(current.language_confidence or 0.0)
                    tenant_id = current.tenant_id
            except SQLAlchemyError:
                # If we cannot load previous, continue with defaults
                pass

            # Look up tenant-level last known if applicable
            last_known: tuple[str, float] | None = None
            if tenant_id:
                try:
                    last_known = await conv_repo.find_last_known_language(tenant_id)
                except SQLAlchemyError:
                    last_known = None

            # Choose language: prefer stronger evidence; reuse last-known if detection weak/unknown
            chosen_lang = prev_lang
            chosen_conf = prev_conf

            # Apply detection if it's stronger than previous/current evidence
            if detected_lang != "unknown":
                if detected_conf >= max(prev_conf, (last_known[1] if last_known else 0.0)):
                    chosen_lang = detected_lang
                    chosen_conf = float(detected_conf)
            # If detection unknown or weaker, and we have a tenant-level last known while prev is unknown, reuse it
            if (chosen_lang == "unknown" or chosen_conf == 0.0) and last_known:
                lk_lang, lk_conf = last_known
                if lk_lang and lk_lang != "unknown":
                    chosen_lang, chosen_conf = lk_lang, float(lk_conf)

            # Persist chosen language
            try:
                await conv_repo.update_language(conversation_id, chosen_lang, float(chosen_conf))
            except SQLAlchemyError:
                logger.warning(
                    "inbound_sms_db_unavailable",
                    request_id=request_id,
                    route="/webhook/twilio/sms",
                    twilio_sid=sid,
                )

            # Logging decision audit
            logger.info(
                "language_decision",
                request_id=request_id,
                route="/webhook/twilio/sms",
                twilio_sid=sid,
                tenant_id=tenant_id,
                language_prev=prev_lang,
                language_new=detected_lang,
                confidence_prev=prev_conf,
                confidence_new=detected_conf,
                chosen=chosen_lang,
            )

            # Update external tenant profile if configured and changed with sufficient confidence
            try:
                settings = get_settings()
                if tenant_id and chosen_lang != "unknown" and chosen_conf >= 0.7 and chosen_lang != prev_lang:
                    tp = TenantProfileClient(settings.tenant_profile_api_url)
                    _ = await tp.update_language(tenant_id, chosen_lang)
            except Exception:
                # Swallow errors to keep webhook resilient
                logger.warning(
                    "tenant_profile_update_error",
                    request_id=request_id,
                    route="/webhook/twilio/sms",
                    twilio_sid=sid,
                    tenant_id=tenant_id,
                )
        logger.info(
            "inbound_sms_processed",
            request_id=request_id,
            route="/webhook/twilio/sms",
            twilio_sid=sid,
            duplicate=not created,
            phone=from_number,
        )

        # Metrics: unknown conversation created if no tenant match and we just created the conv
        if conv_created and monitor_match is None:
            Metrics.inc("unknown_conversation_created")
            logger.info(
                "unknown_conversation_created",
                request_id=request_id,
                twilio_sid=sid,
                phone=from_number,
                conversation_id=conversation_id,
            )
        return {"processed": created, "duplicate": not created, "id": getattr(entity, "id", None)}
