from __future__ import annotations

import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.metrics import Metrics
from src.adapters.twilio_client import TwilioClient, TwilioError
from src.repositories.conversations import ConversationRepository
from src.repositories.messages import MessageRepository
from src.utils.config import get_settings
from src.utils.retry import retry_async
from src.utils.phone import to_e164, normalize_phone


logger = structlog.get_logger(__name__)


@dataclass
class SendResult:
    id: int
    twilio_sid: str | None
    conversation_id: int | None


class SmsOutboundService:
    def __init__(self, session: AsyncSession, twilio: TwilioClient):
        self.session = session
        self.twilio = twilio
        self.msgs = MessageRepository(session)
        self.convs = ConversationRepository(session)

    async def send(
        self,
        to: str,
        body: str,
        *,
        request_id: str,
        conversation_id: int | None = None,
    ) -> SendResult:
        # Validate body
        if not body or not body.strip():
            raise ValueError("invalid_body")

        # Validate and normalize destination using best-effort E.164
        # Accept numbers that can be canonicalized and look like real phones (>=10 digits)
        orig, canon = normalize_phone(to)
        if not canon:
            raise ValueError("invalid_destination")
        digits = "".join(ch for ch in canon if ch.isdigit())
        if len(digits) < 10:
            raise ValueError("invalid_destination")
        e164 = canon

        # Ensure/lookup conversation by canonical phone
        _, canon = normalize_phone(e164)
        conv_id: int | None = None
        conv = await self.convs.upsert_by_phone(original=to, canon=canon or e164)
        conv_id = conv.id

        # Insert pending outbound row
        entity = await self.msgs.insert_outbound_pending(
            conversation_id=conv_id, to_number=canon or e164, body=body.strip()
        )

        logger.info(
            "outbound_sms_requested",
            request_id=request_id,
            route="/sms/send",
            to=e164,
            conversation_id=conv_id,
            message_id=entity.id,
        )

        # Attempt provider send with retry policy
        settings = get_settings()
        max_tries = int(getattr(settings, "twilio_send_max_retries", 3))
        base_ms = int(getattr(settings, "twilio_send_base_backoff_ms", 100))
        cap_ms = int(getattr(settings, "twilio_send_backoff_cap_ms", 2000))

        def is_retryable(exc: BaseException) -> bool:
            return isinstance(exc, TwilioError) and getattr(exc, "category", None) == "transient"

        def on_retry(attempt: int, backoff_ms: int, exc: BaseException) -> None:
            if isinstance(exc, TwilioError):
                logger.warning(
                    "outbound_sms_retry",
                    request_id=request_id,
                    attempt=attempt,
                    backoff_ms=backoff_ms,
                    error_category=getattr(exc, "category", None),
                    status_code=getattr(exc, "status_code", None),
                    correlation_id=getattr(exc, "correlation_id", None),
                    to=e164,
                    message_id=entity.id,
                )

        try:
            sid = await retry_async(
                self.twilio.send_sms,
                e164,
                body.strip(),
                attempts=max_tries,
                base_ms=base_ms,
                cap_ms=cap_ms,
                is_retryable=is_retryable,
                on_retry=on_retry,
            )
            await self.msgs.set_sent_result(entity.id, sid, status="queued")
            Metrics.inc("outbound_sms_sent")
            logger.info(
                "outbound_sms_sent",
                request_id=request_id,
                route="/sms/send",
                to=e164,
                conversation_id=conv_id,
                twilio_sid=sid,
                message_id=entity.id,
            )
            return SendResult(id=entity.id, twilio_sid=sid, conversation_id=conv_id)
        except TwilioError as ex:
            # Permanent failures -> mark failed; transient exhausted -> keep pending
            category = getattr(ex, "category", None)
            if category == "transient":
                # Retries exhausted; keep as pending for potential later reconciliation
                Metrics.inc(
                    "outbound_sms_failed",
                    category="exhausted",
                    route="/sms/send",
                    status_code=getattr(ex, "status_code", None),
                    correlation_id=getattr(ex, "correlation_id", None),
                )
                logger.error(
                    "outbound_sms_failed",
                    request_id=request_id,
                    route="/sms/send",
                    to=e164,
                    conversation_id=conv_id,
                    message_id=entity.id,
                    error_category="exhausted",
                    status_code=getattr(ex, "status_code", None),
                    correlation_id=getattr(ex, "correlation_id", None),
                    error=str(ex),
                )
                raise
            else:
                await self.msgs.set_failed_result(entity.id, status="failed")
                Metrics.inc(
                    "outbound_sms_failed",
                    category="permanent",
                    route="/sms/send",
                    status_code=getattr(ex, "status_code", None),
                    correlation_id=getattr(ex, "correlation_id", None),
                )
                logger.error(
                    "outbound_sms_failed",
                    request_id=request_id,
                    route="/sms/send",
                    to=e164,
                    conversation_id=conv_id,
                    message_id=entity.id,
                    error_category="permanent",
                    status_code=getattr(ex, "status_code", None),
                    correlation_id=getattr(ex, "correlation_id", None),
                    error=str(ex),
                )
                raise
