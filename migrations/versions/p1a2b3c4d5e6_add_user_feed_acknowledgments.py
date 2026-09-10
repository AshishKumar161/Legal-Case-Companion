"""add user feed acknowledgments table

Revision ID: p1a2b3c4d5e6
Revises: o1a2b3c4d5e6
Create Date: 2026-09-05 20:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "p1a2b3c4d5e6"
down_revision: str | None = "o1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_feed_acknowledgments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("last_acknowledged_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("preferences", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), onupdate=sa.func.current_timestamp(), nullable=False),
    )
    op.create_index("ix_user_feed_acknowledgments_user_id", "user_feed_acknowledgments", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_feed_acknowledgments_user_id", table_name="user_feed_acknowledgments")
    op.drop_table("user_feed_acknowledgments")
