"""Add timeline metadata

Revision ID: a94d9a0dabeb
Revises: b4c8d0e1f3g5
Create Date: 2026-08-23 12:35:48.587350

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a94d9a0dabeb"
down_revision: str | None = "b4c8d0e1f3g5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "case_timeline_events",
        sa.Column(
            "metadata",
            sa.JSON().with_variant(
                postgresql.JSONB(astext_type=sa.Text()), "postgresql"
            ),
            nullable=True,
        ),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    op.drop_column("case_timeline_events", "metadata")
    # ### end Alembic commands ###
