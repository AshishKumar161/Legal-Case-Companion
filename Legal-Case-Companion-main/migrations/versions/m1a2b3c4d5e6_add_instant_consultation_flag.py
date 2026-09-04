"""add instant consultation flag to consultations

Revision ID: m1a2b3c4d5e6
Revises: l1a2b3c4d5e6
Create Date: 2026-09-04 21:40:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m1a2b3c4d5e6"
down_revision: str | None = "l1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "consultations",
        sa.Column("is_instant", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_consultations_is_instant", "consultations", ["is_instant"], unique=False
    )
    op.alter_column("consultations", "is_instant", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_consultations_is_instant", table_name="consultations")
    op.drop_column("consultations", "is_instant")
