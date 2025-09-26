from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20250926_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sms_conversations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("phone_number_canonical", sa.String(length=32), nullable=False),
        sa.Column("phone_number_original", sa.String(length=64), nullable=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=True),
        sa.Column("language_detected", sa.String(length=16), nullable=False, server_default="unknown"),
        sa.Column("language_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("last_message_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_sms_conversations_phone_number_canonical",
        "sms_conversations",
        ["phone_number_canonical"],
        unique=True,
    )

    op.create_table(
        "sms_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("sms_conversations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("twilio_sid", sa.String(length=64), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False, server_default="inbound"),
        sa.Column("from_number", sa.String(length=64), nullable=True),
        sa.Column("to_number", sa.String(length=64), nullable=True),
        sa.Column("message_content", sa.String(length=2000), nullable=True),
        sa.Column("raw_webhook_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sms_messages_twilio_sid", "sms_messages", ["twilio_sid"], unique=True)
    op.create_index("ix_sms_messages_conversation_id", "sms_messages", ["conversation_id"])
    op.create_index("ix_sms_messages_created_at", "sms_messages", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_sms_messages_created_at", table_name="sms_messages")
    op.drop_index("ix_sms_messages_conversation_id", table_name="sms_messages")
    op.drop_index("ix_sms_messages_twilio_sid", table_name="sms_messages")
    op.drop_table("sms_messages")
    op.drop_index("ix_sms_conversations_phone_number_canonical", table_name="sms_conversations")
    op.drop_table("sms_conversations")

