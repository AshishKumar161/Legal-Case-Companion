"""Add raw_legal_sources table

Revision ID: a1b2c3d4e5f6
Revises: 9c0d1e2f3a4b
Create Date: 2026-08-30

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "9c0d1e2f3a4b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Use existing legalauthoritytype enum
    legalauthoritytype_enum = postgresql.ENUM(
        "PRIMARY_LEGISLATION",
        "SUBORDINATE_LEGISLATION",
        "JUDICIAL_DECISION",
        "OFFICIAL_NOTIFICATION",
        "OFFICIAL_CIRCULAR",
        "SECONDARY_MATERIAL",
        name="legalauthoritytype",
        create_type=False,
    )

    op.create_table(
        "raw_legal_sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_system", sa.String(length=100), nullable=False),
        sa.Column("external_identifier", sa.String(length=255), nullable=False),
        sa.Column("source_type", legalauthoritytype_enum, nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("raw_metadata", sa.JSON(), nullable=True),
        sa.Column("content_checksum", sa.String(length=64), nullable=False),
        sa.Column("retrieval_url", sa.String(length=500), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="RAW_INGESTED"),
        sa.Column("canonical_source_id", sa.UUID(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["canonical_source_id"],
            ["legal_sources.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_raw_legal_sources_source_system", "raw_legal_sources", ["source_system"]
    )
    op.create_index(
        "ix_raw_legal_sources_external_identifier", "raw_legal_sources", ["external_identifier"]
    )
    op.create_index(
        "ix_raw_legal_sources_content_checksum", "raw_legal_sources", ["content_checksum"]
    )
    op.create_index(
        "ix_raw_legal_sources_canonical_source_id", "raw_legal_sources", ["canonical_source_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_raw_legal_sources_canonical_source_id", table_name="raw_legal_sources")
    op.drop_index("ix_raw_legal_sources_content_checksum", table_name="raw_legal_sources")
    op.drop_index("ix_raw_legal_sources_external_identifier", table_name="raw_legal_sources")
    op.drop_index("ix_raw_legal_sources_source_system", table_name="raw_legal_sources")
    op.drop_table("raw_legal_sources")
