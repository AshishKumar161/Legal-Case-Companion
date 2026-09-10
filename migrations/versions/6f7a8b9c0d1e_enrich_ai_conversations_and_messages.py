"""enrich_ai_conversations_and_messages

Revision ID: 6f7a8b9c0d1e
Revises: 5e6f7a8b9c0d
Create Date: 2026-08-30 22:42:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6f7a8b9c0d1e"
down_revision: str | None = "5e6f7a8b9c0d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("ai_conversations") as batch_op:
        batch_op.add_column(
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", name="fk_ai_conversations_user_id", ondelete="SET NULL"), nullable=True)
        )
        batch_op.add_column(
            sa.Column("status", sa.String(length=50), nullable=False, server_default="ACTIVE")
        )
        batch_op.add_column(
            sa.Column("metadata", sa.JSON(), nullable=True)
        )
        batch_op.create_index("ix_ai_conversations_user_id", ["user_id"], unique=False)

    with op.batch_alter_table("ai_messages") as batch_op:
        batch_op.add_column(sa.Column("authority_citations", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("claims", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("grounding_status", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("uncertainties", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("model_version", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("latency_ms", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ai_messages") as batch_op:
        batch_op.drop_column("metadata")
        batch_op.drop_column("latency_ms")
        batch_op.drop_column("model_version")
        batch_op.drop_column("uncertainties")
        batch_op.drop_column("grounding_status")
        batch_op.drop_column("claims")
        batch_op.drop_column("authority_citations")

    with op.batch_alter_table("ai_conversations") as batch_op:
        batch_op.drop_index("ix_ai_conversations_user_id")
        batch_op.drop_column("metadata")
        batch_op.drop_column("status")
        batch_op.drop_column("user_id")
