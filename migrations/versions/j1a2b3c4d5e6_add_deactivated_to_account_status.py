"""add deactivated to accountstatus enum

Revision ID: j1a2b3c4d5e6
Revises: i1a2b3c4d5e6
Create Date: 2026-09-04 02:50:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "j1a2b3c4d5e6"
down_revision: str | None = "i1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE accountstatus ADD VALUE IF NOT EXISTS 'DEACTIVATED'")


def downgrade() -> None:
    pass
