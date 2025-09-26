from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

import structlog
from src.db.base import get_session
from src.services.conversations import ConversationService
from src.utils.phone import normalize_phone


router = APIRouter(prefix="/conversations", tags=["conversations"])


class MessageOut(BaseModel):
    id: int
    direction: str
    from_number: str | None
    to_number: str | None
    message_content: str | None
    content: str | None = None
    twilio_sid: str | None = None
    delivery_status: str | None = None
    created_at: str


class ConversationResponse(BaseModel):
    phone_number_canonical: str
    phone_number_original: str | None = None
    tenant_id: Optional[str] = None
    workflow_type: Optional[str] = None
    last_message_at: str | None = None
    messages: List[MessageOut]
    # Optional pagination echoes for clients that care
    page: Optional[int] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    total: Optional[int] = None


@router.get("/{phone_number}", response_model=ConversationResponse)
async def get_conversation(
    phone_number: str,
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    offset: int | None = Query(None, ge=0),
    session: AsyncSession = Depends(get_session),
):
    service = ConversationService(session)
    result = await service.get_with_messages_by_phone(
        phone_number, page=page, limit=limit, offset=offset
    )
    req_id = None
    try:
        req_id = request.headers.get("x-request-id") if request else None
    except Exception:
        req_id = None

    if not result:
        structlog.get_logger().bind(request_id=req_id, phone=phone_number, page=page, limit=limit, offset=offset).info(
            "conversation_retrieval.not_found"
        )
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv = result.conversation
    items = [
        MessageOut(
            id=m.id,
            direction=m.direction,
            from_number=m.from_number,
            to_number=m.to_number,
            message_content=m.message_content,
            content=m.message_content,
            twilio_sid=getattr(m, "twilio_sid", None),
            delivery_status=getattr(m, "delivery_status", None),
            created_at=m.created_at.isoformat(),
        )
        for m in result.messages
    ]
    # Shape matches tests: root fields + messages list
    resp = ConversationResponse(
        phone_number_canonical=conv.phone_number_canonical,
        phone_number_original=conv.phone_number_original,
        tenant_id=getattr(conv, "tenant_id", None),
        workflow_type=getattr(conv, "workflow_type", None),
        last_message_at=conv.last_message_at.isoformat() if conv.last_message_at else None,
        messages=items,
        page=page,
        limit=limit,
        offset=(offset if offset is not None else (page - 1) * limit),
        total=result.total,
    )
    structlog.get_logger().bind(
        request_id=req_id, phone=phone_number, page=page, limit=limit, offset=offset, result="found"
    ).info("conversation_retrieval.found")
    return resp
