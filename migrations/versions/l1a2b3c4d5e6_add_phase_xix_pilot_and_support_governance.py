"""add phase xix pilot experiments, support cases, feedback extensions, ai human reviews, and data quality tables

Revision ID: l1a2b3c4d5e6
Revises: k1a2b3c4d5e6
Create Date: 2026-09-04 04:15:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "l1a2b3c4d5e6"
down_revision: str | None = "k1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Pilot Experiments
    op.create_table(
        "pilot_experiments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("experiment_id", sa.String(length=100), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("cohort", sa.String(length=100), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("success_metrics", sa.JSON(), nullable=False),
        sa.Column("failure_metrics", sa.JSON(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PLANNED", "ACTIVE", "PAUSED", "COMPLETED", "TERMINATED", name="experimentstatus"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pilot_experiments_experiment_id"), "pilot_experiments", ["experiment_id"], unique=True)
    op.create_index(op.f("ix_pilot_experiments_cohort"), "pilot_experiments", ["cohort"], unique=False)
    op.create_index(op.f("ix_pilot_experiments_status"), "pilot_experiments", ["status"], unique=False)

    # 2. Support Cases
    op.create_table(
        "support_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("support_case_id", sa.String(length=50), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column(
            "severity",
            sa.Enum("SEV1_CRITICAL", "SEV2_HIGH", "SEV3_MEDIUM", "SEV4_LOW", name="supportcaseseverity"),
            nullable=False,
        ),
        sa.Column("user_scope", sa.String(length=50), nullable=False),
        sa.Column("workflow", sa.String(length=100), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_response_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum("OPEN", "PENDING_USER", "IN_PROGRESS", "RESOLVED", "CLOSED", name="supportcasestatus"),
            nullable=False,
        ),
        sa.Column("resolution_code", sa.String(length=100), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("escalation_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("assigned_to_user_id", sa.Uuid(), nullable=True),
        sa.Column("linked_incident_id", sa.Uuid(), nullable=True),
        sa.Column("linked_release_id", sa.String(length=100), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["linked_incident_id"], ["production_incidents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_support_cases_support_case_id"), "support_cases", ["support_case_id"], unique=True)
    op.create_index(op.f("ix_support_cases_status"), "support_cases", ["status"], unique=False)
    op.create_index(op.f("ix_support_cases_severity"), "support_cases", ["severity"], unique=False)
    op.create_index(op.f("ix_support_cases_category"), "support_cases", ["category"], unique=False)

    # 3. Enhance Pilot Feedback
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(
            "BUG",
            "USABILITY",
            "FEATURE_REQUEST",
            "LEGAL_RISK",
            "SECURITY_CONCERN",
            "AI_QUALITY",
            "OPERATIONAL",
            name="feedbacktype",
        ).create(bind, checkfirst=True)

    with op.batch_alter_table("pilot_feedback") as batch_op:
        batch_op.add_column(
            sa.Column(
                "feedback_type",
                sa.Enum(
                    "BUG",
                    "USABILITY",
                    "FEATURE_REQUEST",
                    "LEGAL_RISK",
                    "SECURITY_CONCERN",
                    "AI_QUALITY",
                    "OPERATIONAL",
                    name="feedbacktype",
                ),
                nullable=False,
                server_default="USABILITY",
            )
        )
        batch_op.add_column(sa.Column("severity", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("workflow", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("sentiment", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("reproducibility", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("product_priority", sa.String(length=20), nullable=True, server_default="P2"))
        batch_op.add_column(sa.Column("linked_incident_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("linked_release_id", sa.String(length=100), nullable=True))
        batch_op.create_foreign_key("fk_pilot_feedback_incident", "production_incidents", ["linked_incident_id"], ["id"], ondelete="SET NULL")

    # 4. AI Human Reviews
    op.create_table(
        "ai_human_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.String(length=50), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "category",
            sa.Enum(
                "HALLUCINATION",
                "MISSING_CITATION",
                "INCORRECT_CITATION",
                "WRONG_JURISDICTION",
                "OUTDATED_LAW",
                "UNSAFE_RECOMMENDATION",
                "EXCESSIVE_CONFIDENCE",
                "FAILURE_TO_REFUSE",
                "UNNECESSARY_REFUSAL",
                "RETRIEVAL_FAILURE",
                "PROMPT_INJECTION",
                "ACCEPTABLE",
                name="aireviewcategory",
            ),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.Enum("SEV1_CRITICAL", "SEV2_HIGH", "SEV3_MEDIUM", "SEV4_LOW", name="aireviewseverity"),
            nullable=False,
        ),
        sa.Column(
            "review_outcome",
            sa.Enum("CONFIRMED_DEFECT", "FALSE_ALARM", "BENIGN_DISCREPANCY", "TRAINING_GAP", name="aireviewoutcome"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("PENDING", "IN_REVIEW", "ACTIONED", "DISMISSED", name="aireviewstatus"),
            nullable=False,
        ),
        sa.Column("original_prompt_snippet", sa.Text(), nullable=True),
        sa.Column("original_answer_snippet", sa.Text(), nullable=True),
        sa.Column("corrected_interpretation", sa.Text(), nullable=True),
        sa.Column("model_version", sa.String(length=100), nullable=True),
        sa.Column("retrieval_config_version", sa.String(length=100), nullable=True),
        sa.Column("linked_release_id", sa.String(length=100), nullable=True),
        sa.Column("linked_incident_id", sa.Uuid(), nullable=True),
        sa.Column("action_taken", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["linked_incident_id"], ["production_incidents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["message_id"], ["ai_messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_human_reviews_review_id"), "ai_human_reviews", ["review_id"], unique=True)
    op.create_index(op.f("ix_ai_human_reviews_category"), "ai_human_reviews", ["category"], unique=False)
    op.create_index(op.f("ix_ai_human_reviews_status"), "ai_human_reviews", ["status"], unique=False)

    # 5. Data Quality Runs
    op.create_table(
        "data_quality_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.String(length=50), nullable=False),
        sa.Column(
            "run_type",
            sa.Enum("AUDIT_ONLY", "AUDIT_AND_REPAIR", name="dataqualityruntype"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "RUNNING",
                "COMPLETED_CLEAN",
                "COMPLETED_WITH_ANOMALIES",
                "COMPLETED_WITH_REPAIRS",
                "FAILED",
                name="dataqualityrunstatus",
            ),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entities_audited", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("anomalies_detected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("repairs_executed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("anomaly_breakdown", sa.JSON(), nullable=False),
        sa.Column("repair_summary", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("triggered_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("is_automated", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_data_quality_runs_run_id"), "data_quality_runs", ["run_id"], unique=True)
    op.create_index(op.f("ix_data_quality_runs_status"), "data_quality_runs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_table("data_quality_runs")
    op.drop_table("ai_human_reviews")
    with op.batch_alter_table("pilot_feedback") as batch_op:
        batch_op.drop_constraint("fk_pilot_feedback_incident", type_="foreignkey")
        batch_op.drop_column("linked_release_id")
        batch_op.drop_column("linked_incident_id")
        batch_op.drop_column("product_priority")
        batch_op.drop_column("reproducibility")
        batch_op.drop_column("sentiment")
        batch_op.drop_column("workflow")
        batch_op.drop_column("severity")
        batch_op.drop_column("feedback_type")
    op.drop_table("support_cases")
    op.drop_table("pilot_experiments")
