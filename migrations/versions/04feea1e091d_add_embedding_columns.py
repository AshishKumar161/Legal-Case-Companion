"""add_embedding_columns

Revision ID: 04feea1e091d
Revises: e4f8db885ba5
Create Date: 2026-08-27 19:00:13.418191

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "04feea1e091d"
down_revision: str | None = "e4f8db885ba5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.add_column(
            "document_chunks", sa.Column("embedding", sa.JSON(), nullable=True)
        )
    else:
        op.add_column(
            "document_chunks",
            sa.Column("embedding", sa.ARRAY(sa.Float()), nullable=True),
        )
    op.add_column(
        "document_chunks", sa.Column("embedding_model", sa.String(), nullable=True)
    )
    op.add_column(
        "document_chunks", sa.Column("embedding_version", sa.String(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("document_chunks", "embedding_version")
    op.drop_column("document_chunks", "embedding_model")
    op.drop_column("document_chunks", "embedding")
