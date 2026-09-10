"""Add pg_trgm and chunk search indexes

Revision ID: 4d5e6f7a8b9c
Revises: 3c4d5e6f7a8b
Create Date: 2026-08-30

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4d5e6f7a8b9c"
down_revision: str | None = "3c4d5e6f7a8b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. PostgreSQL specific trigram extension and index
    if bind.engine.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_document_chunks_content_trgm "
            "ON document_chunks USING gin (content gin_trgm_ops)"
        )

    # 2. Composite indexes for case-scoped and document-scoped filtering
    op.create_index(
        "ix_document_chunks_case_id_deleted_at",
        "document_chunks",
        ["case_id", "deleted_at"],
        unique=False,
    )
    op.create_index(
        "ix_document_chunks_document_id_deleted_at",
        "document_chunks",
        ["document_id", "deleted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_chunks_document_id_deleted_at",
        table_name="document_chunks",
    )
    op.drop_index(
        "ix_document_chunks_case_id_deleted_at",
        table_name="document_chunks",
    )

    bind = op.get_bind()
    if bind.engine.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_document_chunks_content_trgm")
