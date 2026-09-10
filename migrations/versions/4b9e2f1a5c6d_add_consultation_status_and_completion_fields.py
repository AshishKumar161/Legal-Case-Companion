"""add_consultation_status_and_completion_fields

Revision ID: 4b9e2f1a5c6d
Revises: 3a8f1e2d4c5b
Create Date: 2026-08-30 01:35:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4b9e2f1a5c6d"
down_revision: str | None = "3a8f1e2d4c5b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. In Postgres, add enum values ACCEPTED and REJECTED if using postgres
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE consultationstatus ADD VALUE IF NOT EXISTS 'ACCEPTED'")
        op.execute("ALTER TYPE consultationstatus ADD VALUE IF NOT EXISTS 'REJECTED'")

    # 2. Add completed_at and rejection_reason columns
    with op.batch_alter_table("consultations") as batch_op:
        batch_op.add_column(
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("rejection_reason", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("consultations") as batch_op:
        batch_op.drop_column("rejection_reason")
        batch_op.drop_column("completed_at")
