"""add evidentiary bundles and bsa certificates

Revision ID: u1a2b3c4d5e6
Revises: t1a2b3c4d5e6
Create Date: 2026-09-06 15:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "u1a2b3c4d5e6"
down_revision: str | None = "t1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Update PostgreSQL enums if on postgresql
    if bind.dialect.name == "postgresql":
        from sqlalchemy.dialects import postgresql
        res = bind.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'hearingstatus'")).first()
        if res:
            op.execute("ALTER TYPE hearingstatus ADD VALUE IF NOT EXISTS 'COMPLETED'")
            op.execute("ALTER TYPE hearingstatus ADD VALUE IF NOT EXISTS 'RESCHEDULED'")
        postgresql.ENUM("DRAFT", "GENERATING", "FINALIZED", "FAILED", name="bundlestatus").create(bind, checkfirst=True)

    # 2. Add columns to case_hearings
    op.add_column("case_hearings", sa.Column("court_number", sa.String(50), nullable=True))
    op.add_column("case_hearings", sa.Column("hearing_type", sa.String(100), nullable=True))
    op.add_column("case_hearings", sa.Column("next_date", sa.DateTime(timezone=True), nullable=True))

    # 3. Create evidence_bundles table
    from sqlalchemy.dialects import postgresql
    bundle_status_col = (
        postgresql.ENUM("DRAFT", "GENERATING", "FINALIZED", "FAILED", name="bundlestatus", create_type=False)
        if bind.dialect.name == "postgresql"
        else sa.String(20)
    )

    op.create_table(
        "evidence_bundles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hearing_id", sa.Uuid(), sa.ForeignKey("case_hearings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", bundle_status_col, nullable=False, server_default="DRAFT"),
        sa.Column("bates_prefix", sa.String(20), nullable=False, server_default="LCC"),
        sa.Column("bates_start", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("bates_end", sa.Integer(), nullable=True),
        sa.Column("total_pages", sa.Integer(), nullable=True),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("storage_key", sa.String(512), unique=True, nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("sha256_hash", sa.String(64), nullable=True),
        sa.Column("manifest", sa.JSON(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), onupdate=sa.func.current_timestamp(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_evidence_bundles_case_id", "evidence_bundles", ["case_id"])
    op.create_index("ix_evidence_bundles_hearing_id", "evidence_bundles", ["hearing_id"])
    op.create_index("ix_evidence_bundles_status", "evidence_bundles", ["status"])
    op.create_index("ix_evidence_bundles_sha256_hash", "evidence_bundles", ["sha256_hash"])
    op.create_index("ix_evidence_bundles_created_by_user_id", "evidence_bundles", ["created_by_user_id"])

    # 4. Create evidence_bundle_items table
    op.create_table(
        "evidence_bundle_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("bundle_id", sa.Uuid(), sa.ForeignKey("evidence_bundles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), sa.ForeignKey("evidence.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("evidence_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("exhibit_id", sa.Uuid(), sa.ForeignKey("case_exhibits.id", ondelete="SET NULL"), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("exhibit_number", sa.String(50), nullable=True),
        sa.Column("custom_title", sa.String(255), nullable=True),
        sa.Column("bates_start_page", sa.Integer(), nullable=True),
        sa.Column("bates_end_page", sa.Integer(), nullable=True),
        sa.Column("sha256_hash", sa.String(64), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), onupdate=sa.func.current_timestamp(), nullable=False),
        sa.UniqueConstraint("bundle_id", "order_index", name="uq_bundle_item_order"),
    )
    op.create_index("ix_evidence_bundle_items_bundle_id", "evidence_bundle_items", ["bundle_id"])
    op.create_index("ix_evidence_bundle_items_evidence_id", "evidence_bundle_items", ["evidence_id"])
    op.create_index("ix_evidence_bundle_items_version_id", "evidence_bundle_items", ["version_id"])
    op.create_index("ix_evidence_bundle_items_exhibit_id", "evidence_bundle_items", ["exhibit_id"])

    # 5. Create bsa_certificate_drafts table
    op.create_table(
        "bsa_certificate_drafts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bundle_id", sa.Uuid(), sa.ForeignKey("evidence_bundles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("evidence_id", sa.Uuid(), sa.ForeignKey("evidence.id", ondelete="SET NULL"), nullable=True),
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("evidence_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("record_identification", sa.String(500), nullable=False),
        sa.Column("source_device_type", sa.String(255), nullable=False),
        sa.Column("source_device_details", sa.Text(), nullable=True),
        sa.Column("lawful_control_statement", sa.Text(), nullable=False),
        sa.Column("operational_condition_statement", sa.Text(), nullable=False),
        sa.Column("hash_value", sa.String(64), nullable=False),
        sa.Column("hash_algorithm", sa.String(20), nullable=False, server_default="SHA-256"),
        sa.Column("declarant_name", sa.String(255), nullable=False),
        sa.Column("declarant_designation", sa.String(255), nullable=False),
        sa.Column("declarant_organization", sa.String(255), nullable=True),
        sa.Column("place", sa.String(255), nullable=False),
        sa.Column("declaration_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.String(50), nullable=False, server_default="DRAFT"),
        sa.Column("storage_key", sa.String(512), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), onupdate=sa.func.current_timestamp(), nullable=False),
    )
    op.create_index("ix_bsa_certificate_drafts_case_id", "bsa_certificate_drafts", ["case_id"])
    op.create_index("ix_bsa_certificate_drafts_bundle_id", "bsa_certificate_drafts", ["bundle_id"])
    op.create_index("ix_bsa_certificate_drafts_evidence_id", "bsa_certificate_drafts", ["evidence_id"])
    op.create_index("ix_bsa_certificate_drafts_created_by_user_id", "bsa_certificate_drafts", ["created_by_user_id"])


def downgrade() -> None:
    op.drop_table("bsa_certificate_drafts")
    op.drop_table("evidence_bundle_items")
    op.drop_table("evidence_bundles")
    op.drop_column("case_hearings", "next_date")
    op.drop_column("case_hearings", "hearing_type")
    op.drop_column("case_hearings", "court_number")
