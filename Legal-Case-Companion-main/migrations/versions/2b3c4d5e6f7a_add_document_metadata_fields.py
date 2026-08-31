"""Add document metadata fields

Revision ID: 2b3c4d5e6f7a
Revises: 1a2b3c4d5e6f
Create Date: 2026-08-30

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "2b3c4d5e6f7a"
down_revision: str | None = "1a2b3c4d5e6f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create documentcategory enum in PostgreSQL if not present
    bind = op.get_bind()
    if bind.engine.name == "postgresql":
        document_category_enum = postgresql.ENUM(
            "EVIDENCE",
            "PLEADINGS",
            "COURT_ORDER",
            "CONTRACT",
            "NOTICE",
            "ID_PROOF",
            "MISCELLANEOUS",
            name="documentcategory",
            create_type=False,
        )
        document_category_enum.create(bind, checkfirst=True)

    # 2. Add columns to documents table
    op.add_column(
        "documents",
        sa.Column(
            "document_type",
            sa.Enum(
                "EVIDENCE",
                "PLEADINGS",
                "COURT_ORDER",
                "CONTRACT",
                "NOTICE",
                "ID_PROOF",
                "MISCELLANEOUS",
                name="documentcategory",
            ),
            nullable=False,
            server_default="MISCELLANEOUS",
        ),
    )
    op.add_column(
        "documents",
        sa.Column("description", sa.String(length=1000), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("checksum", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "documents",
        sa.Column(
            "is_confidential",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # 3. Add index for document_type queries
    op.create_index(
        op.f("ix_documents_document_type"),
        "documents",
        ["document_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_documents_document_type"), table_name="documents")
    op.drop_column("documents", "is_confidential")
    op.drop_column("documents", "version")
    op.drop_column("documents", "checksum")
    op.drop_column("documents", "description")
    op.drop_column("documents", "document_type")

    bind = op.get_bind()
    if bind.engine.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS documentcategory")
