from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.base import get_session
from src.repositories.conversations import ConversationRepository
from src.repositories.messages import MessageRepository
from src.utils.phone import normalize_phone


router = APIRouter(prefix="/conversations", tags=["conversations"])


class MessageOut(BaseModel):
    id: int
    direction: str
    from_number: str | None
    to_number: str | None
    message_content: str | None
    created_at: str


class ConversationOut(BaseModel):
    phone_number_canonical: str
    phone_number_original: str | None
    language_detected: str
    language_confidence: float
    last_message_at: str | None
    messages: List[MessageOut]


@router.get("/{phone_number}", response_model=ConversationOut)
async def get_conversation(
    phone_number: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    _orig, canon = normalize_phone(phone_number)
    if not canon:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv_repo = ConversationRepository(session)
    msg_repo = MessageRepository(session)

    conv = await conv_repo.get_by_phone(canon)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msgs = await msg_repo.list_by_conversation(conv.id, limit=limit, offset=offset)
    out = ConversationOut(
        phone_number_canonical=conv.phone_number_canonical,
        phone_number_original=conv.phone_number_original,
        language_detected=conv.language_detected,
        language_confidence=float(conv.language_confidence),
        last_message_at=conv.last_message_at.isoformat() if conv.last_message_at else None,
        messages=[
            MessageOut(
                id=m.id,
                direction=m.direction,
                from_number=m.from_number,
                to_number=m.to_number,
                message_content=m.message_content,
                created_at=m.created_at.isoformat(),
            )
            for m in msgs
        ],
    )
    return out

