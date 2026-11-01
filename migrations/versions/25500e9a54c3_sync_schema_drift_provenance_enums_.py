"""sync_schema_drift_provenance_enums_indices

Revision ID: 25500e9a54c3
Revises: n1a2b3c4d5e6
Create Date: 2026-09-05 13:34:57.937507

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite
import app.models.base

# revision identifiers, used by Alembic.
revision: str = '25500e9a54c3'
down_revision: Union[str, None] = 'n1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    if "feedback" in tables:
        # Data preservation: backfill any legacy feedback rows into pilot_feedback before table drop
        if "pilot_feedback" in tables:
            bind.execute(
                sa.text("""
                    INSERT INTO pilot_feedback (
                        id, user_id, category, feedback_type, description,
                        page_url, status, priority, product_priority, created_at, updated_at
                    )
                    SELECT
                        f.id, f.user_id, f.category, 'BUG', f.content,
                        COALESCE(CAST(f.reference_id AS VARCHAR), 'legacy'), 'RESOLVED', 'P2', 'P2', f.created_at, f.updated_at
                    FROM feedback f
                    WHERE NOT EXISTS (SELECT 1 FROM pilot_feedback pf WHERE pf.id = f.id)
                """)
            )

        if not is_sqlite:
            existing_fb_indexes = {idx["name"] for idx in insp.get_indexes("feedback")}
            idx_name = op.f("ix_feedback_user_id")
            if idx_name in existing_fb_indexes:
                op.drop_index(idx_name, table_name="feedback")
        op.drop_table("feedback")

    # Indices
    for idx_name, tbl, cols in [
        ("ix_ai_human_reviews_conversation_id", "ai_human_reviews", ["conversation_id"]),
        ("ix_ai_human_reviews_linked_incident_id", "ai_human_reviews", ["linked_incident_id"]),
        ("ix_ai_human_reviews_linked_release_id", "ai_human_reviews", ["linked_release_id"]),
        ("ix_ai_human_reviews_message_id", "ai_human_reviews", ["message_id"]),
        ("ix_ai_human_reviews_review_outcome", "ai_human_reviews", ["review_outcome"]),
        ("ix_ai_human_reviews_reviewer_user_id", "ai_human_reviews", ["reviewer_user_id"]),
        ("ix_ai_human_reviews_severity", "ai_human_reviews", ["severity"]),
        ("ix_ai_reviews_cat_outcome", "ai_human_reviews", ["category", "review_outcome"]),
        ("ix_commercial_entitlements_user_id", "commercial_entitlements", ["user_id"]),
        ("ix_consultations_is_instant", "consultations", ["is_instant"]),
        ("ix_consultations_lawyer_scheduled", "consultations", ["lawyer_id", "scheduled_at"]),
        ("ix_consultations_status", "consultations", ["status"]),
        ("ix_data_quality_runs_triggered_by_user_id", "data_quality_runs", ["triggered_by_user_id"]),
    ]:
        if tbl in tables:
            existing_indexes = {idx["name"] for idx in insp.get_indexes(tbl)}
            if idx_name not in existing_indexes:
                op.create_index(idx_name, tbl, cols, unique=False)

    if "translation_messages" in tables:
        tm_indexes = {idx["name"] for idx in insp.get_indexes("translation_messages")}
        if "ix_translation_messages_status" in tm_indexes:
            op.drop_index("ix_translation_messages_status", table_name="translation_messages")
        if "ix_translation_status" not in tm_indexes:
            op.create_index("ix_translation_status", "translation_messages", ["status"], unique=False)

    # Column alterations (PostgreSQL / standard SQL engines)
    if not is_sqlite:
        if bind.dialect.name == "postgresql":
            # 1. Update existing enums with new values
            for val in ['CLIENT_AUTHORIZED', 'LAWYER_ACCEPTED', 'MUTUAL_CONSENT', 'ENDED', 'EXPIRED', 'NO_SHOW']:
                op.execute(f"ALTER TYPE consultationstatus ADD VALUE IF NOT EXISTS '{val}'")
            for val in ['AUTHORIZED', 'CAPTURED', 'PARTIALLY_REFUNDED', 'DISPUTED']:
                op.execute(f"ALTER TYPE paymentstatus ADD VALUE IF NOT EXISTS '{val}'")
            for val in ['LAWYER_SEARCHED', 'LAWYER_SELECTED', 'TASK_CREATED', 'TASK_COMPLETED', 'MATTER_REQUEST_CREATED', 'MATTER_REQUEST_SUBMITTED', 'DECISION_RECORDED', 'HEARING_SCHEDULED', 'ONBOARDING_COMPLETED', 'EVIDENCE_UPLOADED', 'EVIDENCE_REVIEWED', 'CASE_MILESTONE_REACHED', 'LAWYER_VERIFICATION_SUBMITTED', 'LAWYER_VERIFICATION_COMPLETED', 'LAWYER_PROFILE_COMPLETED', 'LAWYER_AVAILABILITY_CONFIGURED', 'CONSULTATION_ACCEPTED', 'ACCOUNT_DELETED']:
                op.execute(f"ALTER TYPE producteventtype ADD VALUE IF NOT EXISTS '{val}'")
            for val in ['REGISTERED', 'VERIFIED', 'RESTRICTED']:
                op.execute(f"ALTER TYPE accountstatus ADD VALUE IF NOT EXISTS '{val}'")

            def convert_varchar_to_enum(table, col, enum_name, enum_values, default=None):
                e = sa.Enum(*enum_values, name=enum_name)
                e.create(bind, checkfirst=True)
                if default is not None:
                    op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} DROP DEFAULT")
                op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} TYPE {enum_name} USING {col}::{enum_name}")
                if default is not None:
                    op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} SET DEFAULT '{default}'::{enum_name}")

            convert_varchar_to_enum("background_jobs", "job_type", "jobtype", [
                "DOCUMENT_PROCESSING", "DOCUMENT_INDEXING", "CASE_INTELLIGENCE_REFRESH", "DEADLINE_REMINDER_SCAN",
                "TASK_OVERDUE_SCAN", "STALE_JOB_RECOVERY", "NOTIFICATION_DELIVERY", "LEGAL_AUTHORITY_INGESTION",
                "LEGAL_AUTHORITY_REINDEX", "EVIDENCE_SCAN_AND_ACTIVATE", "EVIDENCE_INTEGRITY_AUDIT",
                "EVIDENCE_ORPHAN_RECONCILIATION", "ABANDONED_UPLOAD_CLEANUP", "OUTBOX_DISPATCH"
            ])
            convert_varchar_to_enum("background_jobs", "status", "jobstatus", [
                "PENDING", "RUNNING", "SUCCEEDED", "FAILED", "RETRYING", "CANCELLED", "DEAD_LETTER"
            ], default="PENDING")

            fact_status_vals = [
                "AI_SUGGESTED", "AI_VERIFIED", "AI_GENERATED", "SYSTEM_RULE", "SYSTEM_GENERATED",
                "USER_PROVIDED", "LAWYER_VERIFIED", "OFFICIAL_SOURCE", "HUMAN_CONFIRMED", "CONTESTED",
                "USER_REPORTED", "UNVERIFIED"
            ]
            convert_varchar_to_enum("case_chronology_events", "verification_status", "factverificationstatus", fact_status_vals, default="AI_SUGGESTED")
            convert_varchar_to_enum("case_claims_defenses", "verification_status", "factverificationstatus", fact_status_vals, default="AI_SUGGESTED")
            convert_varchar_to_enum("case_facts", "verification_status", "factverificationstatus", fact_status_vals, default="AI_SUGGESTED")
            convert_varchar_to_enum("case_risk_indicators", "verification_status", "factverificationstatus", fact_status_vals, default="AI_SUGGESTED")
            convert_varchar_to_enum("legal_issues", "verification_status", "factverificationstatus", fact_status_vals, default="AI_SUGGESTED")

            convert_varchar_to_enum("evidence", "category", "evidencecategory", [
                "FORENSIC", "FINANCIAL", "CONTRACTUAL", "DIGITAL", "TESTIMONIAL", "REGULATORY", "PHYSICAL_SCAN", "MISCELLANEOUS"
            ], default="MISCELLANEOUS")
            convert_varchar_to_enum("evidence", "status", "evidencestatus", [
                "UPLOADING", "QUARANTINED", "ACTIVE", "REVOKED", "DELETION_PENDING", "DELETED"
            ], default="UPLOADING")
            convert_varchar_to_enum("evidence", "sensitivity", "evidencesensitivity", [
                "STANDARD", "CONFIDENTIAL", "HIGHLY_CONFIDENTIAL", "PRIVILEGED"
            ], default="STANDARD")

            convert_varchar_to_enum("evidence_access_grants", "access_level", "evidenceaccesslevel", [
                "VIEW", "DOWNLOAD", "MANAGE"
            ], default="VIEW")
            convert_varchar_to_enum("evidence_custody_events", "action", "evidencecustodyaction", [
                "UPLOADED", "SCAN_PASSED", "SCAN_FAILED", "SHARED", "ACCESS_REVOKED", "VIEWED", "DOWNLOADED",
                "INTEGRITY_VERIFIED", "INTEGRITY_FAILED", "VERSION_CREATED", "LEGAL_HOLD_APPLIED",
                "LEGAL_HOLD_REMOVED", "DELETION_REQUESTED", "DELETED"
            ])
            convert_varchar_to_enum("evidence_versions", "scan_status", "evidencescanstatus", [
                "PENDING", "VALIDATING", "SCANNING", "PASSED", "FAILED"
            ], default="PENDING")
            convert_varchar_to_enum("evidence_versions", "integrity_status", "evidenceintegritystatus", [
                "UNVERIFIED", "VERIFIED_MATCH", "TAMPER_DETECTED"
            ], default="UNVERIFIED")

            convert_varchar_to_enum("video_meetings", "status", "videomeetingstatus", [
                "SCHEDULED", "ACTIVE", "ENDED", "CANCELLED"
            ], default="SCHEDULED")
            convert_varchar_to_enum("video_recordings", "status", "videorecordingstatus", [
                "PENDING", "CONSENTED", "RECORDING", "UPLOADING", "PROCESSING", "AVAILABLE", "FAILED"
            ], default="PENDING")

            if "evidence" in tables and "evidence_versions" in tables:
                existing_fks = {fk["name"] for fk in insp.get_foreign_keys("evidence")}
                if "fk_evidence_current_version_id" not in existing_fks:
                    op.create_foreign_key("fk_evidence_current_version_id", "evidence", "evidence_versions", ["current_version_id"], ["id"], ondelete="SET NULL", use_alter=True)
        else:
            op.alter_column('background_jobs', 'job_type',
                       existing_type=sa.VARCHAR(length=25),
                       type_=sa.Enum('DOCUMENT_PROCESSING', 'DOCUMENT_INDEXING', 'CASE_INTELLIGENCE_REFRESH', 'DEADLINE_REMINDER_SCAN', 'TASK_OVERDUE_SCAN', 'STALE_JOB_RECOVERY', 'NOTIFICATION_DELIVERY', 'LEGAL_AUTHORITY_INGESTION', 'LEGAL_AUTHORITY_REINDEX', 'EVIDENCE_SCAN_AND_ACTIVATE', 'EVIDENCE_INTEGRITY_AUDIT', 'EVIDENCE_ORPHAN_RECONCILIATION', 'ABANDONED_UPLOAD_CLEANUP', 'OUTBOX_DISPATCH', name='jobtype'),
                       existing_nullable=False)
            op.alter_column('background_jobs', 'status',
                       existing_type=sa.VARCHAR(length=9),
                       type_=sa.Enum('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'RETRYING', 'CANCELLED', 'DEAD_LETTER', name='jobstatus'),
                       existing_nullable=False)
            op.alter_column('case_chronology_events', 'verification_status',
                       existing_type=sa.VARCHAR(length=15),
                       type_=sa.Enum('AI_SUGGESTED', 'AI_VERIFIED', 'AI_GENERATED', 'SYSTEM_RULE', 'SYSTEM_GENERATED', 'USER_PROVIDED', 'LAWYER_VERIFIED', 'OFFICIAL_SOURCE', 'HUMAN_CONFIRMED', 'CONTESTED', 'USER_REPORTED', 'UNVERIFIED', name='factverificationstatus'),
                       existing_nullable=False)
            op.alter_column('case_claims_defenses', 'verification_status',
                       existing_type=sa.VARCHAR(length=15),
                       type_=sa.Enum('AI_SUGGESTED', 'AI_VERIFIED', 'AI_GENERATED', 'SYSTEM_RULE', 'SYSTEM_GENERATED', 'USER_PROVIDED', 'LAWYER_VERIFIED', 'OFFICIAL_SOURCE', 'HUMAN_CONFIRMED', 'CONTESTED', 'USER_REPORTED', 'UNVERIFIED', name='factverificationstatus'),
                       existing_nullable=False)
            op.alter_column('case_facts', 'verification_status',
                       existing_type=sa.VARCHAR(length=15),
                       type_=sa.Enum('AI_SUGGESTED', 'AI_VERIFIED', 'AI_GENERATED', 'SYSTEM_RULE', 'SYSTEM_GENERATED', 'USER_PROVIDED', 'LAWYER_VERIFIED', 'OFFICIAL_SOURCE', 'HUMAN_CONFIRMED', 'CONTESTED', 'USER_REPORTED', 'UNVERIFIED', name='factverificationstatus'),
                       existing_nullable=False)
            op.alter_column('case_risk_indicators', 'verification_status',
                       existing_type=sa.VARCHAR(length=15),
                       type_=sa.Enum('AI_SUGGESTED', 'AI_VERIFIED', 'AI_GENERATED', 'SYSTEM_RULE', 'SYSTEM_GENERATED', 'USER_PROVIDED', 'LAWYER_VERIFIED', 'OFFICIAL_SOURCE', 'HUMAN_CONFIRMED', 'CONTESTED', 'USER_REPORTED', 'UNVERIFIED', name='factverificationstatus'),
                       existing_nullable=False)
            op.alter_column('consultations', 'status',
                       existing_type=sa.VARCHAR(length=11),
                       type_=sa.Enum('CREATED', 'PENDING', 'CLIENT_AUTHORIZED', 'LAWYER_ACCEPTED', 'MUTUAL_CONSENT', 'IN_PROGRESS', 'ENDED', 'CANCELLED', 'REJECTED', 'EXPIRED', 'PAYMENT_FAILED', 'NO_SHOW', 'REQUESTED', 'PAID', 'ACCEPTED', 'SCHEDULED', 'COMPLETED', name='consultationstatus'),
                       existing_nullable=False)
            op.alter_column('evidence', 'category',
                       existing_type=sa.VARCHAR(length=50),
                       type_=sa.Enum('FORENSIC', 'FINANCIAL', 'CONTRACTUAL', 'DIGITAL', 'TESTIMONIAL', 'REGULATORY', 'PHYSICAL_SCAN', 'MISCELLANEOUS', name='evidencecategory'),
                       existing_nullable=False,
                       existing_server_default=sa.text("'MISCELLANEOUS'"))
            op.alter_column('evidence', 'status',
                       existing_type=sa.VARCHAR(length=50),
                       type_=sa.Enum('UPLOADING', 'QUARANTINED', 'ACTIVE', 'REVOKED', 'DELETION_PENDING', 'DELETED', name='evidencestatus'),
                       existing_nullable=False,
                       existing_server_default=sa.text("'UPLOADING'"))
            op.alter_column('evidence', 'sensitivity',
                       existing_type=sa.VARCHAR(length=50),
                       type_=sa.Enum('STANDARD', 'CONFIDENTIAL', 'HIGHLY_CONFIDENTIAL', 'PRIVILEGED', name='evidencesensitivity'),
                       existing_nullable=False,
                       existing_server_default=sa.text("'STANDARD'"))
            if "evidence" in tables and "evidence_versions" in tables:
                existing_fks = {fk["name"] for fk in insp.get_foreign_keys("evidence")}
                if "fk_evidence_current_version_id" not in existing_fks:
                    op.create_foreign_key("fk_evidence_current_version_id", "evidence", "evidence_versions", ["current_version_id"], ["id"], ondelete="SET NULL", use_alter=True)
            op.alter_column('evidence_access_grants', 'access_level',
                       existing_type=sa.VARCHAR(length=50),
                       type_=sa.Enum('VIEW', 'DOWNLOAD', 'MANAGE', name='evidenceaccesslevel'),
                       existing_nullable=False,
                       existing_server_default=sa.text("'VIEW'"))
            op.alter_column('evidence_custody_events', 'action',
                       existing_type=sa.VARCHAR(length=50),
                       type_=sa.Enum('UPLOADED', 'SCAN_PASSED', 'SCAN_FAILED', 'SHARED', 'ACCESS_REVOKED', 'VIEWED', 'DOWNLOADED', 'INTEGRITY_VERIFIED', 'INTEGRITY_FAILED', 'VERSION_CREATED', 'LEGAL_HOLD_APPLIED', 'LEGAL_HOLD_REMOVED', 'DELETION_REQUESTED', 'DELETED', name='evidencecustodyaction'),
                       existing_nullable=False)
            op.alter_column('evidence_versions', 'scan_status',
                       existing_type=sa.VARCHAR(length=50),
                       type_=sa.Enum('PENDING', 'VALIDATING', 'SCANNING', 'PASSED', 'FAILED', name='evidencescanstatus'),
                       existing_nullable=False,
                       existing_server_default=sa.text("'PENDING'"))
            op.alter_column('evidence_versions', 'integrity_status',
                       existing_type=sa.VARCHAR(length=50),
                       type_=sa.Enum('UNVERIFIED', 'VERIFIED_MATCH', 'TAMPER_DETECTED', name='evidenceintegritystatus'),
                       existing_nullable=False,
                       existing_server_default=sa.text("'UNVERIFIED'"))
            op.alter_column('legal_issues', 'verification_status',
                       existing_type=sa.VARCHAR(length=15),
                       type_=sa.Enum('AI_SUGGESTED', 'AI_VERIFIED', 'AI_GENERATED', 'SYSTEM_RULE', 'SYSTEM_GENERATED', 'USER_PROVIDED', 'LAWYER_VERIFIED', 'OFFICIAL_SOURCE', 'HUMAN_CONFIRMED', 'CONTESTED', 'USER_REPORTED', 'UNVERIFIED', name='factverificationstatus'),
                       existing_nullable=False)
            op.alter_column('payments', 'status',
                       existing_type=sa.VARCHAR(length=9),
                       type_=sa.Enum('CREATED', 'PENDING', 'AUTHORIZED', 'CAPTURED', 'SUCCEEDED', 'FAILED', 'REFUNDED', 'PARTIALLY_REFUNDED', 'DISPUTED', 'CANCELLED', name='paymentstatus'),
                       existing_nullable=False)
            op.alter_column('product_events', 'event_type',
                       existing_type=sa.VARCHAR(length=24),
                       type_=sa.Enum('USER_REGISTERED', 'CASE_CREATED', 'CASE_UPDATED', 'LAWYER_SEARCHED', 'LAWYER_SELECTED', 'DOCUMENT_UPLOADED', 'DOCUMENT_PROCESSED', 'INTELLIGENCE_VIEWED', 'COPILOT_QUERIED', 'TASK_CREATED', 'TASK_COMPLETED', 'MATTER_REQUEST_CREATED', 'MATTER_REQUEST_SUBMITTED', 'DECISION_RECORDED', 'HEARING_SCHEDULED', 'CONSULTATION_REQUESTED', 'PAYMENT_CONFIRMED', 'CONSULTATION_COMPLETED', 'AI_REQUESTED', 'ONBOARDING_COMPLETED', 'EVIDENCE_UPLOADED', 'EVIDENCE_REVIEWED', 'CASE_MILESTONE_REACHED', 'LAWYER_VERIFICATION_SUBMITTED', 'LAWYER_VERIFICATION_COMPLETED', 'LAWYER_PROFILE_COMPLETED', 'LAWYER_AVAILABILITY_CONFIGURED', 'CONSULTATION_ACCEPTED', 'ACCOUNT_DELETED', name='producteventtype'),
                       existing_nullable=False)
            op.alter_column('users', 'account_status',
                       existing_type=sa.VARCHAR(length=9),
                       type_=sa.Enum('REGISTERED', 'VERIFIED', 'ACTIVE', 'RESTRICTED', 'SUSPENDED', 'DEACTIVATED', name='accountstatus'),
                       existing_nullable=False)
            op.alter_column('video_meetings', 'status',
                       existing_type=sa.VARCHAR(length=20),
                       type_=sa.Enum('SCHEDULED', 'ACTIVE', 'ENDED', 'CANCELLED', name='videomeetingstatus'),
                       existing_nullable=False,
                       existing_server_default=sa.text("'SCHEDULED'"))
            op.alter_column('video_recordings', 'status',
                       existing_type=sa.VARCHAR(length=20),
                       type_=sa.Enum('PENDING', 'CONSENTED', 'RECORDING', 'UPLOADING', 'PROCESSING', 'AVAILABLE', 'FAILED', name='videorecordingstatus'),
                       existing_nullable=False,
                       existing_server_default=sa.text("'PENDING'"))


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if not is_sqlite:
        if bind.dialect.name == "postgresql":
            insp_down = sa.inspect(bind)
            if "evidence" in insp_down.get_table_names():
                existing_fks = {fk["name"] for fk in insp_down.get_foreign_keys("evidence")}
                if "fk_evidence_current_version_id" in existing_fks:
                    op.drop_constraint("fk_evidence_current_version_id", "evidence", type_="foreignkey")

            def convert_enum_to_varchar(table, col, length, default=None):
                if default is not None:
                    op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} DROP DEFAULT")
                op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} TYPE VARCHAR({length}) USING {col}::VARCHAR")
                if default is not None:
                    op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} SET DEFAULT '{default}'")

            convert_enum_to_varchar("background_jobs", "job_type", 25)
            convert_enum_to_varchar("background_jobs", "status", 9, default="PENDING")
            for tbl in ["case_chronology_events", "case_claims_defenses", "case_facts", "case_risk_indicators", "legal_issues"]:
                convert_enum_to_varchar(tbl, "verification_status", 15, default="AI_SUGGESTED")
            convert_enum_to_varchar("evidence", "category", 50, default="MISCELLANEOUS")
            convert_enum_to_varchar("evidence", "status", 50, default="UPLOADING")
            convert_enum_to_varchar("evidence", "sensitivity", 50, default="STANDARD")
            convert_enum_to_varchar("evidence_access_grants", "access_level", 50, default="VIEW")
            convert_enum_to_varchar("evidence_custody_events", "action", 50)
            convert_enum_to_varchar("evidence_versions", "scan_status", 50, default="PENDING")
            convert_enum_to_varchar("evidence_versions", "integrity_status", 50, default="UNVERIFIED")
            convert_enum_to_varchar("video_meetings", "status", 20, default="SCHEDULED")
            convert_enum_to_varchar("video_recordings", "status", 20, default="PENDING")
        else:
            op.alter_column('video_recordings', 'status',
                       existing_type=sa.Enum('PENDING', 'CONSENTED', 'RECORDING', 'UPLOADING', 'PROCESSING', 'AVAILABLE', 'FAILED', name='videorecordingstatus'),
                       type_=sa.VARCHAR(length=20),
                       existing_nullable=False,
                       existing_server_default=sa.text("'PENDING'"))
            op.alter_column('video_meetings', 'status',
                       existing_type=sa.Enum('SCHEDULED', 'ACTIVE', 'ENDED', 'CANCELLED', name='videomeetingstatus'),
                       type_=sa.VARCHAR(length=20),
                       existing_nullable=False,
                       existing_server_default=sa.text("'SCHEDULED'"))
            op.alter_column('users', 'account_status',
                       existing_type=sa.Enum('REGISTERED', 'VERIFIED', 'ACTIVE', 'RESTRICTED', 'SUSPENDED', 'DEACTIVATED', name='accountstatus'),
                       type_=sa.VARCHAR(length=9),
                       existing_nullable=False)
            op.alter_column('product_events', 'event_type',
                       existing_type=sa.Enum('USER_REGISTERED', 'CASE_CREATED', 'CASE_UPDATED', 'LAWYER_SEARCHED', 'LAWYER_SELECTED', 'DOCUMENT_UPLOADED', 'DOCUMENT_PROCESSED', 'INTELLIGENCE_VIEWED', 'COPILOT_QUERIED', 'TASK_CREATED', 'TASK_COMPLETED', 'MATTER_REQUEST_CREATED', 'MATTER_REQUEST_SUBMITTED', 'DECISION_RECORDED', 'HEARING_SCHEDULED', 'CONSULTATION_REQUESTED', 'PAYMENT_CONFIRMED', 'CONSULTATION_COMPLETED', 'AI_REQUESTED', 'ONBOARDING_COMPLETED', 'EVIDENCE_UPLOADED', 'EVIDENCE_REVIEWED', 'CASE_MILESTONE_REACHED', 'LAWYER_VERIFICATION_SUBMITTED', 'LAWYER_VERIFICATION_COMPLETED', 'LAWYER_PROFILE_COMPLETED', 'LAWYER_AVAILABILITY_CONFIGURED', 'CONSULTATION_ACCEPTED', 'ACCOUNT_DELETED', name='producteventtype'),
                       type_=sa.VARCHAR(length=24),
                       existing_nullable=False)
            op.alter_column('payments', 'status',
                       existing_type=sa.Enum('CREATED', 'PENDING', 'AUTHORIZED', 'CAPTURED', 'SUCCEEDED', 'FAILED', 'REFUNDED', 'PARTIALLY_REFUNDED', 'DISPUTED', 'CANCELLED', name='paymentstatus'),
                       type_=sa.VARCHAR(length=9),
                       existing_nullable=False)
            op.alter_column('legal_issues', 'verification_status',
                       existing_type=sa.Enum('AI_SUGGESTED', 'AI_VERIFIED', 'AI_GENERATED', 'SYSTEM_RULE', 'SYSTEM_GENERATED', 'USER_PROVIDED', 'LAWYER_VERIFIED', 'OFFICIAL_SOURCE', 'HUMAN_CONFIRMED', 'CONTESTED', 'USER_REPORTED', 'UNVERIFIED', name='factverificationstatus'),
                       type_=sa.VARCHAR(length=15),
                       existing_nullable=False)
            op.alter_column('evidence_versions', 'integrity_status',
                       existing_type=sa.Enum('UNVERIFIED', 'VERIFIED_MATCH', 'TAMPER_DETECTED', name='evidenceintegritystatus'),
                       type_=sa.VARCHAR(length=50),
                       existing_nullable=False,
                       existing_server_default=sa.text("'UNVERIFIED'"))
            op.alter_column('evidence_versions', 'scan_status',
                       existing_type=sa.Enum('PENDING', 'VALIDATING', 'SCANNING', 'PASSED', 'FAILED', name='evidencescanstatus'),
                       type_=sa.VARCHAR(length=50),
                       existing_nullable=False,
                       existing_server_default=sa.text("'PENDING'"))
            op.alter_column('evidence_custody_events', 'action',
                       existing_type=sa.Enum('UPLOADED', 'SCAN_PASSED', 'SCAN_FAILED', 'SHARED', 'ACCESS_REVOKED', 'VIEWED', 'DOWNLOADED', 'INTEGRITY_VERIFIED', 'INTEGRITY_FAILED', 'VERSION_CREATED', 'LEGAL_HOLD_APPLIED', 'LEGAL_HOLD_REMOVED', 'DELETION_REQUESTED', 'DELETED', name='evidencecustodyaction'),
                       type_=sa.VARCHAR(length=50),
                       existing_nullable=False)
            op.alter_column('evidence_access_grants', 'access_level',
                       existing_type=sa.Enum('VIEW', 'DOWNLOAD', 'MANAGE', name='evidenceaccesslevel'),
                       type_=sa.VARCHAR(length=50),
                       existing_nullable=False,
                       existing_server_default=sa.text("'VIEW'"))
            insp_down = sa.inspect(bind)
            if "evidence" in insp_down.get_table_names():
                existing_fks = {fk["name"] for fk in insp_down.get_foreign_keys("evidence")}
                if "fk_evidence_current_version_id" in existing_fks:
                    op.drop_constraint("fk_evidence_current_version_id", "evidence", type_="foreignkey")
            op.alter_column('evidence', 'sensitivity',
                       existing_type=sa.Enum('STANDARD', 'CONFIDENTIAL', 'HIGHLY_CONFIDENTIAL', 'PRIVILEGED', name='evidencesensitivity'),
                       type_=sa.VARCHAR(length=50),
                       existing_nullable=False,
                       existing_server_default=sa.text("'STANDARD'"))
            op.alter_column('evidence', 'status',
                       existing_type=sa.Enum('UPLOADING', 'QUARANTINED', 'ACTIVE', 'REVOKED', 'DELETION_PENDING', 'DELETED', name='evidencestatus'),
                       type_=sa.VARCHAR(length=50),
                       existing_nullable=False,
                       existing_server_default=sa.text("'UPLOADING'"))
            op.alter_column('evidence', 'category',
                       existing_type=sa.Enum('FORENSIC', 'FINANCIAL', 'CONTRACTUAL', 'DIGITAL', 'TESTIMONIAL', 'REGULATORY', 'PHYSICAL_SCAN', 'MISCELLANEOUS', name='evidencecategory'),
                       type_=sa.VARCHAR(length=50),
                       existing_nullable=False,
                       existing_server_default=sa.text("'MISCELLANEOUS'"))
            op.alter_column('consultations', 'status',
                       existing_type=sa.Enum('CREATED', 'PENDING', 'CLIENT_AUTHORIZED', 'LAWYER_ACCEPTED', 'MUTUAL_CONSENT', 'IN_PROGRESS', 'ENDED', 'CANCELLED', 'REJECTED', 'EXPIRED', 'PAYMENT_FAILED', 'NO_SHOW', 'REQUESTED', 'PAID', 'ACCEPTED', 'SCHEDULED', 'COMPLETED', name='consultationstatus'),
                       type_=sa.VARCHAR(length=11),
                       existing_nullable=False)
            op.alter_column('case_risk_indicators', 'verification_status',
                       existing_type=sa.Enum('AI_SUGGESTED', 'AI_VERIFIED', 'AI_GENERATED', 'SYSTEM_RULE', 'SYSTEM_GENERATED', 'USER_PROVIDED', 'LAWYER_VERIFIED', 'OFFICIAL_SOURCE', 'HUMAN_CONFIRMED', 'CONTESTED', 'USER_REPORTED', 'UNVERIFIED', name='factverificationstatus'),
                       type_=sa.VARCHAR(length=15),
                       existing_nullable=False)
            op.alter_column('case_facts', 'verification_status',
                       existing_type=sa.Enum('AI_SUGGESTED', 'AI_VERIFIED', 'AI_GENERATED', 'SYSTEM_RULE', 'SYSTEM_GENERATED', 'USER_PROVIDED', 'LAWYER_VERIFIED', 'OFFICIAL_SOURCE', 'HUMAN_CONFIRMED', 'CONTESTED', 'USER_REPORTED', 'UNVERIFIED', name='factverificationstatus'),
                       type_=sa.VARCHAR(length=15),
                       existing_nullable=False)
            op.alter_column('case_claims_defenses', 'verification_status',
                       existing_type=sa.Enum('AI_SUGGESTED', 'AI_VERIFIED', 'AI_GENERATED', 'SYSTEM_RULE', 'SYSTEM_GENERATED', 'USER_PROVIDED', 'LAWYER_VERIFIED', 'OFFICIAL_SOURCE', 'HUMAN_CONFIRMED', 'CONTESTED', 'USER_REPORTED', 'UNVERIFIED', name='factverificationstatus'),
                       type_=sa.VARCHAR(length=15),
                       existing_nullable=False)
            op.alter_column('case_chronology_events', 'verification_status',
                       existing_type=sa.Enum('AI_SUGGESTED', 'AI_VERIFIED', 'AI_GENERATED', 'SYSTEM_RULE', 'SYSTEM_GENERATED', 'USER_PROVIDED', 'LAWYER_VERIFIED', 'OFFICIAL_SOURCE', 'HUMAN_CONFIRMED', 'CONTESTED', 'USER_REPORTED', 'UNVERIFIED', name='factverificationstatus'),
                       type_=sa.VARCHAR(length=15),
                       existing_nullable=False)
            op.alter_column('background_jobs', 'status',
                       existing_type=sa.Enum('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'RETRYING', 'CANCELLED', 'DEAD_LETTER', name='jobstatus'),
                       type_=sa.VARCHAR(length=9),
                       existing_nullable=False)
            op.alter_column('background_jobs', 'job_type',
                       existing_type=sa.Enum('DOCUMENT_PROCESSING', 'DOCUMENT_INDEXING', 'CASE_INTELLIGENCE_REFRESH', 'DEADLINE_REMINDER_SCAN', 'TASK_OVERDUE_SCAN', 'STALE_JOB_RECOVERY', 'NOTIFICATION_DELIVERY', 'LEGAL_AUTHORITY_INGESTION', 'LEGAL_AUTHORITY_REINDEX', 'EVIDENCE_SCAN_AND_ACTIVATE', 'EVIDENCE_INTEGRITY_AUDIT', 'EVIDENCE_ORPHAN_RECONCILIATION', 'ABANDONED_UPLOAD_CLEANUP', 'OUTBOX_DISPATCH', name='jobtype'),
                       type_=sa.VARCHAR(length=25),
                       existing_nullable=False)

    insp_down = sa.inspect(bind)
    tables_down = insp_down.get_table_names()
    for idx_name, tbl in [
        ('ix_translation_status', 'translation_messages'),
        ('ix_data_quality_runs_triggered_by_user_id', 'data_quality_runs'),
        ('ix_consultations_status', 'consultations'),
        ('ix_consultations_lawyer_scheduled', 'consultations'),
        ('ix_consultations_is_instant', 'consultations'),
        ('ix_commercial_entitlements_user_id', 'commercial_entitlements'),
        ('ix_ai_reviews_cat_outcome', 'ai_human_reviews'),
        ('ix_ai_human_reviews_severity', 'ai_human_reviews'),
        ('ix_ai_human_reviews_reviewer_user_id', 'ai_human_reviews'),
        ('ix_ai_human_reviews_review_outcome', 'ai_human_reviews'),
        ('ix_ai_human_reviews_message_id', 'ai_human_reviews'),
        ('ix_ai_human_reviews_linked_release_id', 'ai_human_reviews'),
        ('ix_ai_human_reviews_linked_incident_id', 'ai_human_reviews'),
        ('ix_ai_human_reviews_conversation_id', 'ai_human_reviews'),
    ]:
        if tbl in tables_down:
            existing_indexes = {idx["name"] for idx in insp_down.get_indexes(tbl)}
            if idx_name in existing_indexes:
                op.drop_index(idx_name, table_name=tbl)

    # Recreate feedback table on downgrade to preserve symmetric schema rollback
    if "feedback" not in tables_down:
        from sqlalchemy.dialects import postgresql
        fb_cat_type = sa.Enum("AI_QUALITY", "BUG", "LAWYER", "GENERAL", name="feedbackcategory").with_variant(
            postgresql.ENUM("AI_QUALITY", "BUG", "LAWYER", "GENERAL", name="feedbackcategory", create_type=False),
            "postgresql",
        )
        op.create_table(
            "feedback",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column(
                "category",
                fb_cat_type,
                nullable=False,
            ),
            sa.Column("reference_id", sa.Uuid(), nullable=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        if not is_sqlite:
            op.create_index(op.f("ix_feedback_user_id"), "feedback", ["user_id"], unique=False)
