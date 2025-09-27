from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func, UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SmsConversation(Base):
    """SMS conversation keyed by canonical phone number.

    Language detection and last activity are stored here.
    """
    __tablename__ = "sms_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Canonical phone number in E.164. Unique per conversation.
    phone_number_canonical: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    # Original phone representation from the first message (best effort).
    phone_number_original: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Language fields
    language_detected: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    language_confidence: Mapped[float] = mapped_column(default=0.0)

    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    messages: Mapped[list["SmsMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class SmsMessage(Base):
    """Inbound/outbound SMS message record with idempotency guard on twilio_sid."""
    __tablename__ = "sms_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("sms_conversations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # Twilio SID may be unknown at insert time for outbound messages
    twilio_sid: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)

    # Direction and addressing
    direction: Mapped[str] = mapped_column(String(16), nullable=False, default="inbound")
    from_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    to_number: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Content and raw webhook payload
    message_content: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # Use SQLite JSON type alias; for Postgres this would be JSONB
    raw_webhook_data: Mapped[dict | None] = mapped_column(SQLITE_JSON, nullable=True)

    # Delivery status for outbound messages (e.g., pending|queued|sent|failed|...)
    delivery_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    conversation: Mapped[SmsConversation | None] = relationship(back_populates="messages")


class SmsMessageStatusEvent(Base):
    """History of outbound SMS delivery status callbacks.

    Records each Twilio status callback snapshot idempotently via an event hash
    unique per (message_id, event_hash).
    """

    __tablename__ = "sms_message_status_events"
    __table_args__ = (
        UniqueConstraint("message_id", "event_hash", name="uq_status_event_hash_per_message"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(
        ForeignKey("sms_messages.id", ondelete="CASCADE"), index=True
    )
    event_status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Hash of salient event properties for idempotency (e.g., status + error + payload)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_webhook_data: Mapped[dict | None] = mapped_column(SQLITE_JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )
