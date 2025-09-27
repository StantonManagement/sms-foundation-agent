from __future__ import annotations

import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.twilio_client import TwilioClient, TwilioConfig, TwilioError
from src.db.base import get_session
from src.services.sms_outbound import SmsOutboundService
from src.utils.config import Settings, get_settings


router = APIRouter(prefix="/sms", tags=["sms"])
logger = structlog.get_logger(__name__)


class SendSmsRequest(BaseModel):
    to: str = Field(..., description="Destination phone number")
    body: str = Field(..., description="Message body")
    conversation_id: Optional[int] = Field(None, description="Optional conversation id")


class SendSmsResponse(BaseModel):
    id: str
    twilio_sid: Optional[str] = None
    conversation_id: Optional[int] = None


def get_twilio_client(settings: Settings = Depends(get_settings)) -> TwilioClient:
    cfg = TwilioConfig(
        account_sid=settings.twilio_account_sid,
        auth_token=settings.twilio_auth_token,
        from_number=settings.twilio_phone_number,
    )
    return TwilioClient(cfg)


@router.post("/send", status_code=status.HTTP_202_ACCEPTED, response_model=SendSmsResponse)
async def send_sms(
    payload: SendSmsRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    twilio: TwilioClient = Depends(get_twilio_client),
):
    request_id = str(uuid.uuid4())

    # Basic validation: non-empty body
    if not payload.body or not payload.body.strip():
        logger.info(
            "outbound_sms_validation_error",
            request_id=request_id,
            route="/sms/send",
            reason="empty_body",
        )
        raise HTTPException(status_code=400, detail="body must not be empty")

    # Service orchestration
    service = SmsOutboundService(session, twilio)
    try:
        result = await service.send(
            payload.to, payload.body, request_id=request_id, conversation_id=payload.conversation_id
        )
        return SendSmsResponse(id=str(result.id), twilio_sid=result.twilio_sid, conversation_id=result.conversation_id)
    except ValueError as ve:
        # Validation errors (e.g., invalid phone)
        logger.info(
            "outbound_sms_validation_error",
            request_id=request_id,
            route="/sms/send",
            reason=str(ve),
        )
        raise HTTPException(status_code=400, detail="invalid request")
    except TwilioError as te:
        # Map provider errors to ApiError envelope
        category = getattr(te, "category", None)
        status_code = getattr(te, "status_code", None)
        corr = getattr(te, "correlation_id", None)

        # Permanent errors -> 4xx, Transient/exhausted -> 502
        http_status = 502
        if category == "permanent":
            http_status = 400 if not isinstance(status_code, int) else (status_code if 400 <= status_code < 500 else 400)

        payload = {
            "error": {
                "code": "sms.external_failed",
                "message": "external provider failure",
                "details": {
                    "category": category or "unknown",
                    "status_code": status_code,
                    "correlation_id": corr,
                },
                "request_id": request_id,
            }
        }
        logger.warning(
            "outbound_sms_provider_error",
            request_id=request_id,
            route="/sms/send",
            error=str(te),
            error_category=category,
            status_code=status_code,
            correlation_id=corr,
        )
        return JSONResponse(status_code=http_status, content=payload)
