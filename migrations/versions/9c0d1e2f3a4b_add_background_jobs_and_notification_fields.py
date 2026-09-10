"""add_background_jobs_and_notification_fields

Revision ID: 9c0d1e2f3a4b
Revises: 8b9c0d1e2f3a
Create Date: 2026-08-30 23:18:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9c0d1e2f3a4b"
down_revision: str | None = "8b9c0d1e2f3a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create background_jobs table
    op.create_table(
        "background_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="PENDING"),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=100), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("error_category", sa.String(length=50), nullable=True),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("result_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_background_jobs_job_type", "background_jobs", ["job_type"])
    op.create_index("ix_background_jobs_status", "background_jobs", ["status"])
    op.create_index("ix_background_jobs_idempotency_key", "background_jobs", ["idempotency_key"], unique=True)
    op.create_index("ix_background_jobs_scheduled_at", "background_jobs", ["scheduled_at"])
    op.create_index("ix_background_jobs_locked_until", "background_jobs", ["locked_until"])
    op.create_index("ix_background_jobs_case_id", "background_jobs", ["case_id"])
    op.create_index("ix_background_jobs_created_by_user_id", "background_jobs", ["created_by_user_id"])
    op.create_index("ix_background_jobs_status_scheduled", "background_jobs", ["status", "scheduled_at"])
    op.create_index("ix_background_jobs_claim", "background_jobs", ["status", "scheduled_at", "locked_until"])

    # 2. Enrich notifications table with deadline_id, hearing_id, document_id
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.add_column(sa.Column("deadline_id", sa.Uuid(), sa.ForeignKey("case_deadlines.id", name="fk_notifications_deadline_id", ondelete="SET NULL"), nullable=True))
        batch_op.add_column(sa.Column("hearing_id", sa.Uuid(), sa.ForeignKey("case_hearings.id", name="fk_notifications_hearing_id", ondelete="SET NULL"), nullable=True))
        batch_op.add_column(sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", name="fk_notifications_document_id", ondelete="SET NULL"), nullable=True))
        batch_op.create_index("ix_notifications_deadline_id", ["deadline_id"])
        batch_op.create_index("ix_notifications_hearing_id", ["hearing_id"])
        batch_op.create_index("ix_notifications_document_id", ["document_id"])


def downgrade() -> None:
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.drop_index("ix_notifications_document_id")
        batch_op.drop_index("ix_notifications_hearing_id")
        batch_op.drop_index("ix_notifications_deadline_id")
        batch_op.drop_column("document_id")
        batch_op.drop_column("hearing_id")
        batch_op.drop_column("deadline_id")

    op.drop_table("background_jobs")
