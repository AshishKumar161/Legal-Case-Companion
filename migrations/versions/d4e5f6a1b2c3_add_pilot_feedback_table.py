"""Add pilot_feedback table

Revision ID: d4e5f6a1b2c3
Revises: c3d4e5f6a1b2
Create Date: 2026-08-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a1b2c3"
down_revision: str | None = "c3d4e5f6a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pilot_feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", name="fk_pilot_feedback_user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "category",
            sa.String(length=50),
            server_default="OTHER",
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("page_url", sa.String(length=500), nullable=False),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="NEW", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pilot_feedback_user_id", "pilot_feedback", ["user_id"])
    op.create_index("ix_pilot_feedback_category", "pilot_feedback", ["category"])
    op.create_index("ix_pilot_feedback_created_at", "pilot_feedback", ["created_at"])


def downgrade() -> None:
    op.drop_table("pilot_feedback")
