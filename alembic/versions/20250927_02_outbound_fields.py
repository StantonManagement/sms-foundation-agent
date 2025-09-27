from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20250927_02"
down_revision = "20250926_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add delivery_status column
    op.add_column(
        "sms_messages",
        sa.Column("delivery_status", sa.String(length=32), nullable=True),
    )
    # Make twilio_sid nullable to allow pending outbound rows
    try:
        op.alter_column(
            "sms_messages",
            "twilio_sid",
            existing_type=sa.String(length=64),
            nullable=True,
        )
    except Exception:
        # Some SQLite backends may not support ALTER COLUMN; acceptable in dev
        pass


def downgrade() -> None:
    try:
        op.alter_column(
            "sms_messages",
            "twilio_sid",
            existing_type=sa.String(length=64),
            nullable=False,
        )
    except Exception:
        pass
    op.drop_column("sms_messages", "delivery_status")

