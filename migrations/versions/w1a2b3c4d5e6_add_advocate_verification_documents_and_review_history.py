"""add advocate verification documents and review history

Revision ID: w1a2b3c4d5e6
Revises: v1a2b3c4d5e6
Create Date: 2026-09-06 17:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "w1a2b3c4d5e6"
down_revision: str | None = "v1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Update PostgreSQL enums if on postgresql
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE verificationstatus ADD VALUE IF NOT EXISTS 'DRAFT'")
        op.execute("ALTER TYPE verificationstatus ADD VALUE IF NOT EXISTS 'NEEDS_INFO'")
        op.execute("ALTER TYPE verificationstatus ADD VALUE IF NOT EXISTS 'REVOKED'")

    # 2. Add columns to lawyer_verifications via batch_alter_table
    with op.batch_alter_table("lawyer_verifications") as batch_op:
        batch_op.add_column(sa.Column("verification_source", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("source_reference", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("verification_method", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("declared_practice_jurisdictions", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("reviewer_notes", sa.Text(), nullable=True))

    # 3. Create advocate_verification_documents table
    op.create_table(
        "advocate_verification_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "verification_id",
            sa.Uuid(),
            sa.ForeignKey("lawyer_verifications.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "document_type",
            sa.Enum(
                "BAR_COUNCIL_ENROLLMENT_CERT",
                "BAR_COUNCIL_ID_CARD",
                "GOVERNMENT_PHOTO_ID",
                "CERTIFICATE_OF_PRACTICE",
                name="advocatedocumenttype",
            ),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("sha256_hash", sa.String(64), nullable=False),
        sa.Column(
            "scan_status",
            sa.Enum(
                "PENDING",
                "PASSED",
                "FAILED",
                "QUARANTINED",
                name="documentscanstatus_v2",
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "verification_status",
            sa.Enum(
                "NOT_SUBMITTED",
                "SUBMITTED",
                "UNDER_REVIEW",
                "APPROVED",
                "REJECTED",
                "NEEDS_RESUBMISSION",
                name="documentverificationstatus",
            ),
            nullable=False,
            server_default="SUBMITTED",
        ),
        sa.Column("rejection_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 4. Create verification_review_events table
    op.create_table(
        "verification_review_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "verification_id",
            sa.Uuid(),
            sa.ForeignKey("lawyer_verifications.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "reviewer_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("from_status", sa.String(50), nullable=False),
        sa.Column("to_status", sa.String(50), nullable=False),
        sa.Column("decision", sa.String(50), nullable=False),
        sa.Column("verification_method", sa.String(100), nullable=True),
        sa.Column("verification_source", sa.String(255), nullable=True),
        sa.Column("source_reference", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("verification_review_events")
    op.drop_table("advocate_verification_documents")

    with op.batch_alter_table("lawyer_verifications") as batch_op:
        batch_op.drop_column("reviewer_notes")
        batch_op.drop_column("last_reviewed_at")
        batch_op.drop_column("verified_at")
        batch_op.drop_column("declared_practice_jurisdictions")
        batch_op.drop_column("verification_method")
        batch_op.drop_column("source_reference")
        batch_op.drop_column("verification_source")
