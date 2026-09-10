"""add case exhibits and evidence tags

Revision ID: t1a2b3c4d5e6
Revises: s1a2b3c4d5e6
Create Date: 2026-09-06 14:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "t1a2b3c4d5e6"
down_revision: str | None = "s1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Update PostgreSQL enums if on postgresql
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE evidencestatus ADD VALUE IF NOT EXISTS 'ARCHIVED'")
        op.execute("ALTER TYPE evidencecustodyaction ADD VALUE IF NOT EXISTS 'ARCHIVED'")
        op.execute("ALTER TYPE evidencecustodyaction ADD VALUE IF NOT EXISTS 'RESTORED'")
        op.execute("ALTER TYPE evidencecustodyaction ADD VALUE IF NOT EXISTS 'TAGS_UPDATED'")
        op.execute("ALTER TYPE evidencecustodyaction ADD VALUE IF NOT EXISTS 'CATEGORY_UPDATED'")
        op.execute("ALTER TYPE evidencecustodyaction ADD VALUE IF NOT EXISTS 'EXHIBIT_CREATED'")
        op.execute("ALTER TYPE evidencecustodyaction ADD VALUE IF NOT EXISTS 'EXHIBIT_RENUMBERED'")

    # 2. Add tags column to evidence table
    op.add_column(
        "evidence",
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
    )

    # 3. Create case_exhibits table
    op.create_table(
        "case_exhibits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), sa.ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("evidence_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("hearing_id", sa.Uuid(), sa.ForeignKey("case_hearings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("exhibit_number", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("relevant_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), onupdate=sa.func.current_timestamp(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("case_id", "exhibit_number", name="uq_case_exhibits_case_number"),
    )
    op.create_index("ix_case_exhibits_case_id", "case_exhibits", ["case_id"])
    op.create_index("ix_case_exhibits_evidence_id", "case_exhibits", ["evidence_id"])
    op.create_index("ix_case_exhibits_version_id", "case_exhibits", ["version_id"])
    op.create_index("ix_case_exhibits_hearing_id", "case_exhibits", ["hearing_id"])
    op.create_index("ix_case_exhibits_created_by_user_id", "case_exhibits", ["created_by_user_id"])


def downgrade() -> None:
    op.drop_index("ix_case_exhibits_created_by_user_id", table_name="case_exhibits")
    op.drop_index("ix_case_exhibits_hearing_id", table_name="case_exhibits")
    op.drop_index("ix_case_exhibits_version_id", table_name="case_exhibits")
    op.drop_index("ix_case_exhibits_evidence_id", table_name="case_exhibits")
    op.drop_index("ix_case_exhibits_case_id", table_name="case_exhibits")
    op.drop_table("case_exhibits")
    op.drop_column("evidence", "tags")
