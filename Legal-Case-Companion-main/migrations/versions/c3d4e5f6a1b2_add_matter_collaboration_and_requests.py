"""Add matter collaboration messages and requests tables

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2026-08-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a1b2"
down_revision: str | None = "b2c3d4e5f6a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create case_messages table
    op.create_table(
        "case_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "case_id",
            sa.Uuid(),
            sa.ForeignKey("cases.id", name="fk_case_messages_case_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sender_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", name="fk_case_messages_sender_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "message_type",
            sa.String(length=50),
            server_default="GENERAL",
            nullable=False,
        ),
        sa.Column(
            "linked_document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", name="fk_case_messages_linked_doc_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "linked_task_id",
            sa.Uuid(),
            sa.ForeignKey("case_tasks.id", name="fk_case_messages_linked_task_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_counsel_only", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_case_messages_case_id", "case_messages", ["case_id"])
    op.create_index("ix_case_messages_sender_id", "case_messages", ["sender_id"])
    op.create_index("ix_case_messages_case_created", "case_messages", ["case_id", "created_at"])

    # 2. Create matter_requests table
    op.create_table(
        "matter_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "case_id",
            sa.Uuid(),
            sa.ForeignKey("cases.id", name="fk_matter_requests_case_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "requesting_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", name="fk_matter_requests_requesting_user_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "assigned_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", name="fk_matter_requests_assigned_user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "request_type",
            sa.String(length=50),
            server_default="DOCUMENT_UPLOAD",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "submitted_document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", name="fk_matter_requests_submitted_doc_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("response_notes", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reviewed_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", name="fk_matter_requests_reviewed_by_user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_matter_requests_case_id", "matter_requests", ["case_id"])
    op.create_index("ix_matter_requests_requesting_user_id", "matter_requests", ["requesting_user_id"])
    op.create_index("ix_matter_requests_assigned_user_id", "matter_requests", ["assigned_user_id"])
    op.create_index("ix_matter_requests_case_status", "matter_requests", ["case_id", "status"])


def downgrade() -> None:
    op.drop_table("matter_requests")
    op.drop_table("case_messages")
