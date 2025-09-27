from __future__ import annotations

import base64
import hmac
import uuid
from hashlib import sha1
from typing import Mapping

import structlog
from fastapi import APIRouter, Depends, Request, Response, status

from src.utils.config import Settings, get_settings
from src.db.base import get_session_maker
from src.services.sms_inbound import SmsInboundService
from src.services.status_service import StatusService


logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/webhook/twilio", tags=["webhooks", "twilio"])


def _compute_twilio_signature(url: str, params: Mapping[str, str], auth_token: str) -> str:
    """Compute Twilio signature for form-encoded requests.

    Algorithm per Twilio docs:
    1) Start with the full URL (including query string if present)
    2) Append each POST param as name+value in lexicographic order of the names
    3) HMAC-SHA1 with auth token as key, then base64 encode
    """
    # Sort by parameter name
    pieces = [url]
    for k in sorted(params.keys()):
        pieces.append(k)
        pieces.append(str(params[k]))
    to_sign = "".join(pieces).encode("utf-8")
    digest = hmac.new(auth_token.encode("utf-8"), to_sign, sha1).digest()
    return base64.b64encode(digest).decode("ascii")


@router.post("/sms")
async def twilio_sms_webhook(
    request: Request, settings: Settings = Depends(get_settings)
) -> Response:
    # Extract signature header
    provided_sig = request.headers.get("X-Twilio-Signature", "")

    # Parse form params
    form = await request.form()
    # Convert to a simple dict[str, str]
    params: dict[str, str] = {k: str(v) for k, v in form.items()}

    # Compute expected signature using exact request URL
    url = str(request.url)
    expected_sig = _compute_twilio_signature(url, params, settings.twilio_auth_token)

    request_id = str(uuid.uuid4())
    if not hmac.compare_digest(provided_sig, expected_sig):
        logger.warning(
            "twilio_webhook_auth_failed",
            request_id=request_id,
            path=str(request.url.path),
        )
        return Response(status_code=status.HTTP_403_FORBIDDEN)

    # Valid: log minimal context with MessageSid if present
    message_sid = params.get("MessageSid")
    log_kwargs = {"request_id": request_id}
    if message_sid:
        log_kwargs["twilio_sid"] = message_sid
    logger.info("twilio_webhook_received", **log_kwargs)

    # Idempotent processing based on MessageSid
    service = SmsInboundService()
    # Use session maker lazily after signature validation to avoid DB cost for rejects
    maker = session_maker_provider()
    async with maker() as session:  # type: ignore[misc]
        await service.handle_inbound(params, session, request_id=request_id)

    # Fast ACK with empty body
    return Response(status_code=status.HTTP_200_OK)


@router.post("/status")
async def twilio_status_webhook(
    request: Request, settings: Settings = Depends(get_settings)
) -> Response:
    provided_sig = request.headers.get("X-Twilio-Signature", "")
    form = await request.form()
    params: dict[str, str] = {k: str(v) for k, v in form.items()}

    url = str(request.url)
    expected_sig = _compute_twilio_signature(url, params, settings.twilio_auth_token)

    request_id = str(uuid.uuid4())
    if not hmac.compare_digest(provided_sig, expected_sig):
        logger.warning(
            "twilio_webhook_auth_failed",
            request_id=request_id,
            path=str(request.url.path),
        )
        return Response(status_code=status.HTTP_403_FORBIDDEN)

    message_sid = params.get("MessageSid")
    log_kwargs = {"request_id": request_id}
    if message_sid:
        log_kwargs["twilio_sid"] = message_sid
    logger.info("twilio_status_webhook_received", **log_kwargs)

    service = StatusService()
    maker = session_maker_provider()
    async with maker() as session:  # type: ignore[misc]
        await service.process_status(params, session, request_id=request_id)

    return Response(status_code=status.HTTP_200_OK)

# Allow tests to override the session maker provider
session_maker_provider = get_session_maker
