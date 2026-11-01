"""add instant consultation flag to consultations

Revision ID: n1a2b3c4d5e6
Revises: m1a2b3c4d5e6
Create Date: 2026-09-04 21:40:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "n1a2b3c4d5e6"
down_revision: str | None = "m1a2b3c4d5e6"
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
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.alter_column("consultations", "is_instant", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    indexes = {idx["name"] for idx in insp.get_indexes("consultations")}
    if "ix_consultations_is_instant" in indexes:
        op.drop_index("ix_consultations_is_instant", table_name="consultations")
    op.drop_column("consultations", "is_instant")
