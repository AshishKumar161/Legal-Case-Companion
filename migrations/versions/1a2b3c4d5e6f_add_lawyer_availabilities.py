"""Add lawyer_availabilities table

Revision ID: 1a2b3c4d5e6f
Revises: 8f1e2d3c4b5a
Create Date: 2026-08-30

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1a2b3c4d5e6f"
down_revision: str | None = "8f1e2d3c4b5a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lawyer_availabilities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lawyer_profile_id", sa.Uuid(), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column(
            "slot_duration_minutes",
            sa.Integer(),
            nullable=False,
            server_default="30",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["lawyer_profile_id"],
            ["lawyer_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_lawyer_availabilities_lawyer_profile_id"),
        "lawyer_availabilities",
        ["lawyer_profile_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lawyer_availabilities_day_of_week"),
        "lawyer_availabilities",
        ["day_of_week"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_lawyer_availabilities_day_of_week"),
        table_name="lawyer_availabilities",
    )
    op.drop_index(
        op.f("ix_lawyer_availabilities_lawyer_profile_id"),
        table_name="lawyer_availabilities",
    )
    op.drop_table("lawyer_availabilities")
