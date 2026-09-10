"""add_case_intelligence_tables

Revision ID: 7a8b9c0d1e2f
Revises: 6f7a8b9c0d1e
Create Date: 2026-08-30 22:56:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7a8b9c0d1e2f"
down_revision: str | None = "6f7a8b9c0d1e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. case_facts
    op.create_table(
        "case_facts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fact_text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False, server_default="GENERAL"),
        sa.Column("verification_status", sa.String(length=50), nullable=False, server_default="AI_SUGGESTED"),
        sa.Column("source_type", sa.String(length=50), nullable=False, server_default="CASE_EVIDENCE"),
        sa.Column("source_chunk_id", sa.Uuid(), sa.ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_filename", sa.String(length=255), nullable=True),
        sa.Column("source_authority_id", sa.String(length=255), nullable=True),
        sa.Column("source_message_id", sa.Uuid(), sa.ForeignKey("ai_messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("document_version", sa.Integer(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_case_facts_case_id", "case_facts", ["case_id"])
    op.create_index("ix_case_facts_source_chunk_id", "case_facts", ["source_chunk_id"])
    op.create_index("ix_case_facts_source_document_id", "case_facts", ["source_document_id"])
    op.create_index("ix_case_facts_source_message_id", "case_facts", ["source_message_id"])

    # 2. legal_issues
    op.create_table(
        "legal_issues",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("issue_text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False, server_default="GENERAL"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="IDENTIFIED"),
        sa.Column("verification_status", sa.String(length=50), nullable=False, server_default="AI_SUGGESTED"),
        sa.Column("supporting_fact_ids", sa.JSON(), nullable=True),
        sa.Column("relevant_authority_ids", sa.JSON(), nullable=True),
        sa.Column("uncertainties", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_legal_issues_case_id", "legal_issues", ["case_id"])

    # 3. case_claims_defenses
    op.create_table(
        "case_claims_defenses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position_type", sa.String(length=50), nullable=False, server_default="CLAIM"),
        sa.Column("party_role", sa.String(length=100), nullable=False, server_default="CLIENT"),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="ASSERTED"),
        sa.Column("verification_status", sa.String(length=50), nullable=False, server_default="AI_SUGGESTED"),
        sa.Column("supporting_chunk_ids", sa.JSON(), nullable=True),
        sa.Column("opposing_chunk_ids", sa.JSON(), nullable=True),
        sa.Column("relevant_authority_ids", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_case_claims_defenses_case_id", "case_claims_defenses", ["case_id"])

    # 4. case_chronology_events
    op.create_table(
        "case_chronology_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("date_text", sa.String(length=100), nullable=True),
        sa.Column("date_precision", sa.String(length=50), nullable=False, server_default="EXACT_DATE"),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_conflicting", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("conflicting_source_details", sa.JSON(), nullable=True),
        sa.Column("source_chunk_id", sa.Uuid(), sa.ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_filename", sa.String(length=255), nullable=True),
        sa.Column("verification_status", sa.String(length=50), nullable=False, server_default="AI_SUGGESTED"),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_case_chronology_events_case_id", "case_chronology_events", ["case_id"])
    op.create_index("ix_case_chronology_events_event_date", "case_chronology_events", ["event_date"])

    # 5. case_evidence_gaps
    op.create_table(
        "case_evidence_gaps",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("gap_type", sa.String(length=50), nullable=False, server_default="MISSING_DOCUMENT"),
        sa.Column("severity", sa.String(length=50), nullable=False, server_default="MEDIUM"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="NOT_FOUND_IN_AVAILABLE_MATERIALS"),
        sa.Column("related_issue_id", sa.Uuid(), sa.ForeignKey("legal_issues.id", ondelete="SET NULL"), nullable=True),
        sa.Column("related_claim_id", sa.Uuid(), sa.ForeignKey("case_claims_defenses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_case_evidence_gaps_case_id", "case_evidence_gaps", ["case_id"])
    op.create_index("ix_case_evidence_gaps_related_issue_id", "case_evidence_gaps", ["related_issue_id"])
    op.create_index("ix_case_evidence_gaps_related_claim_id", "case_evidence_gaps", ["related_claim_id"])

    # 6. case_risk_indicators
    op.create_table(
        "case_risk_indicators",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("risk_title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=50), nullable=False, server_default="MEDIUM"),
        sa.Column("mitigation_hint", sa.Text(), nullable=True),
        sa.Column("evidence_sources", sa.JSON(), nullable=True),
        sa.Column("verification_status", sa.String(length=50), nullable=False, server_default="AI_SUGGESTED"),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_case_risk_indicators_case_id", "case_risk_indicators", ["case_id"])


def downgrade() -> None:
    op.drop_table("case_risk_indicators")
    op.drop_table("case_evidence_gaps")
    op.drop_table("case_chronology_events")
    op.drop_table("case_claims_defenses")
    op.drop_table("legal_issues")
    op.drop_table("case_facts")
