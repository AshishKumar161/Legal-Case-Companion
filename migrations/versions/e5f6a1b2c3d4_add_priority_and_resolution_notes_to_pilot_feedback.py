"""Add priority and resolution_notes to pilot_feedback

Revision ID: e5f6a1b2c3d4
Revises: d4e5f6a1b2c3
Create Date: 2026-09-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a1b2c3d4"
down_revision: str | None = "d4e5f6a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("pilot_feedback", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "priority",
                sa.String(length=20),
                server_default="P2",
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("resolution_notes", sa.Text(), nullable=True)
        )
        batch_op.create_index(
            "ix_pilot_feedback_priority", ["priority"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("pilot_feedback", schema=None) as batch_op:
        batch_op.drop_index("ix_pilot_feedback_priority")
        batch_op.drop_column("resolution_notes")
        batch_op.drop_column("priority")
