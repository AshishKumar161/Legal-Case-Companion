"""add_workflow_deadlines_and_hearings

Revision ID: 8b9c0d1e2f3a
Revises: 7a8b9c0d1e2f
Create Date: 2026-08-30 23:05:30.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8b9c0d1e2f3a"
down_revision: str | None = "7a8b9c0d1e2f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Enrich case_tasks
    op.add_column("case_tasks", sa.Column("source_type", sa.String(length=50), nullable=False, server_default="MANUAL"))
    op.add_column("case_tasks", sa.Column("source_reference", sa.String(length=255), nullable=True))
    op.add_column("case_tasks", sa.Column("is_confirmed", sa.Boolean(), nullable=False, server_default="1"))

    # 2. Create case_deadlines
    op.create_table(
        "case_deadlines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_type", sa.String(length=50), nullable=False, server_default="GENERAL"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="UPCOMING"),
        sa.Column("source_type", sa.String(length=50), nullable=False, server_default="MANUAL"),
        sa.Column("source_reference", sa.String(length=255), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_case_deadlines_case_id", "case_deadlines", ["case_id"])
    op.create_index("ix_case_deadlines_deadline_at", "case_deadlines", ["deadline_at"])
    op.create_index("ix_case_deadlines_status", "case_deadlines", ["status"])

    # 3. Create case_hearings
    op.create_table(
        "case_hearings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("court_name", sa.String(length=255), nullable=False),
        sa.Column("hearing_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("purpose", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="SCHEDULED"),
        sa.Column("bench_or_coram", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False, server_default="MANUAL"),
        sa.Column("source_reference", sa.String(length=255), nullable=True),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_case_hearings_case_id", "case_hearings", ["case_id"])
    op.create_index("ix_case_hearings_hearing_at", "case_hearings", ["hearing_at"])
    op.create_index("ix_case_hearings_status", "case_hearings", ["status"])

    # 4. Create case_reminders
    op.create_table(
        "case_reminders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="PENDING"),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_case_reminders_case_id", "case_reminders", ["case_id"])
    op.create_index("ix_case_reminders_target_id", "case_reminders", ["target_id"])
    op.create_index("ix_case_reminders_remind_at", "case_reminders", ["remind_at"])


def downgrade() -> None:
    op.drop_table("case_reminders")
    op.drop_table("case_hearings")
    op.drop_table("case_deadlines")
    op.drop_column("case_tasks", "is_confirmed")
    op.drop_column("case_tasks", "source_reference")
    op.drop_column("case_tasks", "source_type")
