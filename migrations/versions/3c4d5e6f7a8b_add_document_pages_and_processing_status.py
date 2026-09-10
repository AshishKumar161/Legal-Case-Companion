"""Add document pages and processing status

Revision ID: 3c4d5e6f7a8b
Revises: 2b3c4d5e6f7a
Create Date: 2026-08-30

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "3c4d5e6f7a8b"
down_revision: str | None = "2b3c4d5e6f7a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create documentprocessingstatus enum in PostgreSQL if not present
    bind = op.get_bind()
    if bind.engine.name == "postgresql":
        doc_proc_status_enum = postgresql.ENUM(
            "PENDING",
            "PROCESSING",
            "READY",
            "FAILED",
            "UNSUPPORTED_FORMAT",
            "CORRUPTED_FILE",
            "EMPTY_DOCUMENT",
            "OCR_REQUIRED",
            name="documentprocessingstatus",
            create_type=False,
        )
        doc_proc_status_enum.create(bind, checkfirst=True)

    # 2. Add columns to documents table
    op.add_column(
        "documents",
        sa.Column(
            "processing_status",
            sa.Enum(
                "PENDING",
                "PROCESSING",
                "READY",
                "FAILED",
                "UNSUPPORTED_FORMAT",
                "CORRUPTED_FILE",
                "EMPTY_DOCUMENT",
                "OCR_REQUIRED",
                name="documentprocessingstatus",
            ),
            nullable=False,
            server_default="PENDING",
        ),
    )
    op.add_column(
        "documents",
        sa.Column("processing_error", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("page_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("word_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("character_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        op.f("ix_documents_processing_status"),
        "documents",
        ["processing_status"],
        unique=False,
    )

    # 3. Create document_pages table
    op.create_table(
        "document_pages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("character_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "page_number", name="uq_document_pages_doc_page"),
    )
    op.create_index(op.f("ix_document_pages_document_id"), "document_pages", ["document_id"], unique=False)
    op.create_index(op.f("ix_document_pages_case_id"), "document_pages", ["case_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_document_pages_case_id"), table_name="document_pages")
    op.drop_index(op.f("ix_document_pages_document_id"), table_name="document_pages")
    op.drop_table("document_pages")

    op.drop_index(op.f("ix_documents_processing_status"), table_name="documents")
    op.drop_column("documents", "processed_at")
    op.drop_column("documents", "character_count")
    op.drop_column("documents", "word_count")
    op.drop_column("documents", "page_count")
    op.drop_column("documents", "processing_error")
    op.drop_column("documents", "processing_status")

    bind = op.get_bind()
    if bind.engine.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS documentprocessingstatus")
