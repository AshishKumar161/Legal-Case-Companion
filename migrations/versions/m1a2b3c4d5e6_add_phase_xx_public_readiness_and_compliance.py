"""add phase xx public readiness, compliance registry, legal documents, commercial transactions, and localization

Revision ID: m1a2b3c4d5e6
Revises: l1a2b3c4d5e6
Create Date: 2026-09-04 04:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m1a2b3c4d5e6"
down_revision: str | None = "l1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Translation Messages
    op.create_table(
        "translation_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_key", sa.String(length=255), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("locale", sa.String(length=20), nullable=False),
        sa.Column("translation", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "REVIEW", "APPROVED", "DEPRECATED", name="translationstatus"),
            nullable=False,
        ),
        sa.Column("review_status", sa.String(length=50), nullable=False, server_default="PENDING"),
        sa.Column("version", sa.String(length=50), nullable=False, server_default="1.0.0"),
        sa.Column("reviewed_by", sa.String(length=255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_translation_locale_key", "translation_messages", ["locale", "source_key"], unique=True)
    op.create_index(op.f("ix_translation_messages_source_key"), "translation_messages", ["source_key"], unique=False)
    op.create_index(op.f("ix_translation_messages_locale"), "translation_messages", ["locale"], unique=False)
    op.create_index(op.f("ix_translation_messages_status"), "translation_messages", ["status"], unique=False)

    # 2. Compliance Registry Items
    op.create_table(
        "compliance_registry_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("compliance_item_id", sa.String(length=100), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("requirement_question", sa.Text(), nullable=False),
        sa.Column("technical_control", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("owner", sa.String(length=100), nullable=False),
        sa.Column("legal_reviewer", sa.String(length=100), nullable=True),
        sa.Column(
            "status",
            sa.Enum("OPEN", "IN_REVIEW", "CONDITIONALLY_APPROVED", "APPROVED", "BLOCKED", "NOT_APPLICABLE", name="complianceitemstatus"),
            nullable=False,
        ),
        sa.Column("technical_readiness", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("contractual_readiness", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("policy_readiness", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("legal_approval", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision", sa.String(length=255), nullable=True),
        sa.Column("follow_up", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_compliance_registry_items_compliance_item_id"), "compliance_registry_items", ["compliance_item_id"], unique=True)
    op.create_index("ix_compliance_status", "compliance_registry_items", ["status"], unique=False)
    op.create_index("ix_compliance_owner", "compliance_registry_items", ["owner"], unique=False)

    # 3. Legal Document Versions
    op.create_table(
        "legal_document_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "document_type",
            sa.Enum("TERMS_OF_SERVICE", "ADVOCATE_TERMS", "PRIVACY_NOTICE", "AI_DISCLOSURE", "EVIDENCE_STORAGE_DISCLOSURE", "CONSULTATION_DISCLOSURE", "COOKIE_NOTICE", name="legaldocumenttype"),
            nullable=False,
        ),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("locale", sa.String(length=20), nullable=False, server_default="en-IN"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary_of_changes", sa.Text(), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("supersedes_version_id", sa.Uuid(), nullable=True),
        sa.Column("approval_status", sa.String(length=50), nullable=False, server_default="DRAFT"),
        sa.Column("publication_status", sa.String(length=50), nullable=False, server_default="DRAFT"),
        sa.Column("approved_by", sa.String(length=255), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_version_id"], ["legal_document_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_legal_doc_type_ver_locale", "legal_document_versions", ["document_type", "version", "locale"], unique=True)
    op.create_index("ix_legal_doc_publication", "legal_document_versions", ["publication_status"], unique=False)

    # 4. User Document Consents
    op.create_table(
        "user_document_consents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("document_version_id", sa.Uuid(), nullable=False),
        sa.Column(
            "document_type",
            sa.Enum("TERMS_OF_SERVICE", "ADVOCATE_TERMS", "PRIVACY_NOTICE", "AI_DISCLOSURE", "EVIDENCE_STORAGE_DISCLOSURE", "CONSULTATION_DISCLOSURE", "COOKIE_NOTICE", name="legaldocumenttype"),
            nullable=False,
        ),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("locale", sa.String(length=20), nullable=False, server_default="en-IN"),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("user_agent_hash", sa.String(length=64), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_version_id"], ["legal_document_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_consent_user_doc", "user_document_consents", ["user_id", "document_type", "version"], unique=False)
    op.create_index(op.f("ix_user_document_consents_user_id"), "user_document_consents", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_document_consents_document_version_id"), "user_document_consents", ["document_version_id"], unique=False)

    # 5. Commercial Transactions
    op.create_table(
        "commercial_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.String(length=100), nullable=False),
        sa.Column("consultation_id", sa.Uuid(), nullable=False),
        sa.Column("payer_user_id", sa.Uuid(), nullable=False),
        sa.Column("payee_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "transaction_type",
            sa.Enum("PAYMENT", "REFUND", "PARTIAL_REFUND", "DISPUTE_HOLD", name="transactiontype"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("PENDING", "AUTHORIZED", "CAPTURED", "FAILED", "REFUNDED", "PARTIALLY_REFUNDED", "DISPUTED", "CANCELLED", name="transactionstatus"),
            nullable=False,
        ),
        sa.Column("gross_amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("platform_fee", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0.0"),
        sa.Column("tax_amount", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0.0"),
        sa.Column("net_advocate_amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="INR"),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="STRIPE"),
        sa.Column("provider_transaction_id", sa.String(length=255), nullable=True),
        sa.Column("invoice_number", sa.String(length=100), nullable=True),
        sa.Column("reconciliation_status", sa.String(length=50), nullable=False, server_default="PENDING"),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["consultation_id"], ["consultations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payee_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payer_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_transaction_id"),
        sa.UniqueConstraint("invoice_number"),
    )
    op.create_index(op.f("ix_commercial_transactions_transaction_id"), "commercial_transactions", ["transaction_id"], unique=True)
    op.create_index(op.f("ix_commercial_transactions_consultation_id"), "commercial_transactions", ["consultation_id"], unique=False)
    op.create_index(op.f("ix_commercial_transactions_payer_user_id"), "commercial_transactions", ["payer_user_id"], unique=False)
    op.create_index(op.f("ix_commercial_transactions_payee_user_id"), "commercial_transactions", ["payee_user_id"], unique=False)
    op.create_index(op.f("ix_commercial_transactions_status"), "commercial_transactions", ["status"], unique=False)
    op.create_index("ix_commercial_tx_status_created", "commercial_transactions", ["status", "created_at"], unique=False)

    # 6. Commercial Entitlements
    op.create_table(
        "commercial_entitlements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("entitlement_type", sa.String(length=100), nullable=False),
        sa.Column("quota_limit", sa.Integer(), nullable=False),
        sa.Column("quota_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_entitlement_user_type", "commercial_entitlements", ["user_id", "entitlement_type"], unique=False)

    # 7. Add columns to users
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("account_locale", sa.String(length=20), nullable=False, server_default="en-IN"))
        batch_op.add_column(sa.Column("preferred_language", sa.String(length=10), nullable=False, server_default="en"))
        batch_op.add_column(sa.Column("fallback_language", sa.String(length=10), nullable=False, server_default="en"))

    # 8. Add columns to lawyer_verifications
    with op.batch_alter_table("lawyer_verifications") as batch_op:
        batch_op.add_column(sa.Column("evidence_document_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("rejection_reason_category", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("is_reverification", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    with op.batch_alter_table("lawyer_verifications") as batch_op:
        batch_op.drop_column("is_reverification")
        batch_op.drop_column("rejection_reason_category")
        batch_op.drop_column("expires_at")
        batch_op.drop_column("evidence_document_id")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("fallback_language")
        batch_op.drop_column("preferred_language")
        batch_op.drop_column("account_locale")

    op.drop_table("commercial_entitlements")
    op.drop_table("commercial_transactions")
    op.drop_table("user_document_consents")
    op.drop_table("legal_document_versions")
    op.drop_table("compliance_registry_items")
    op.drop_table("translation_messages")
