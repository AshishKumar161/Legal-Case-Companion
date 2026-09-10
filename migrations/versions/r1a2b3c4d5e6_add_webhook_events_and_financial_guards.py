"""add webhook events and financial guards

Revision ID: r1a2b3c4d5e6
Revises: q1a2b3c4d5e6
Create Date: 2026-09-06 11:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "r1a2b3c4d5e6"
down_revision: str | None = "q1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. processed_webhook_events table
    op.create_table(
        "processed_webhook_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_id", sa.String(150), unique=True, nullable=False),
        sa.Column("provider", sa.String(50), default="STRIPE", nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), default="PROCESSED", nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), onupdate=sa.func.current_timestamp(), nullable=False),
    )
    op.create_index("ix_processed_webhook_events_event_id", "processed_webhook_events", ["event_id"], unique=True)
    op.create_index("ix_processed_webhook_events_provider_event", "processed_webhook_events", ["provider", "event_id"])
    op.create_index("ix_processed_webhook_events_resource_id", "processed_webhook_events", ["resource_id"])


def downgrade() -> None:
    op.drop_index("ix_processed_webhook_events_resource_id", table_name="processed_webhook_events")
    op.drop_index("ix_processed_webhook_events_provider_event", table_name="processed_webhook_events")
    op.drop_index("ix_processed_webhook_events_event_id", table_name="processed_webhook_events")
    op.drop_table("processed_webhook_events")
