"""create_notifications_table

Revision ID: 5c8a1b2e3f4d
Revises: 4b9e2f1a5c6d
Create Date: 2026-08-30 01:48:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5c8a1b2e3f4d"
down_revision: str | None = "4b9e2f1a5c6d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    notification_type_enum = sa.Enum(
        "CASE_CREATED",
        "CASE_STATUS_CHANGED",
        "PARTICIPANT_ADDED",
        "LAWYER_ASSIGNED",
        "TASK_ASSIGNED",
        "TASK_DUE_SOON",
        "TASK_COMPLETED",
        "CONSULTATION_REQUESTED",
        "CONSULTATION_ACCEPTED",
        "CONSULTATION_REJECTED",
        "CONSULTATION_SCHEDULED",
        "CONSULTATION_CANCELLED",
        "CONSULTATION_COMPLETED",
        "PAYMENT_CREATED",
        "PAYMENT_SUCCEEDED",
        "PAYMENT_FAILED",
        "PAYMENT_REFUNDED",
        name="notificationtype",
    )
    notification_type_enum.create(op.get_bind(), checkfirst=True)

    # Create notifications table
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("type", notification_type_enum, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.String(length=1000), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=True),
        sa.Column("consultation_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("event_id", sa.String(length=255), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["consultation_id"], ["consultations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["task_id"], ["case_tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_notifications_case_id"), "notifications", ["case_id"], unique=False
    )
    op.create_index(
        op.f("ix_notifications_consultation_id"),
        "notifications",
        ["consultation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_event_id"), "notifications", ["event_id"], unique=False
    )
    op.create_index(
        op.f("ix_notifications_is_read"), "notifications", ["is_read"], unique=False
    )
    op.create_index(
        op.f("ix_notifications_task_id"), "notifications", ["task_id"], unique=False
    )
    op.create_index(
        op.f("ix_notifications_type"), "notifications", ["type"], unique=False
    )
    op.create_index(
        op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False
    )
    op.create_index(
        "ix_notifications_user_is_read_created",
        "notifications",
        ["user_id", "is_read", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_user_event_type",
        "notifications",
        ["user_id", "event_id", "type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("notifications")

    notification_type_enum = sa.Enum(
        "CASE_CREATED",
        "CASE_STATUS_CHANGED",
        "PARTICIPANT_ADDED",
        "LAWYER_ASSIGNED",
        "TASK_ASSIGNED",
        "TASK_DUE_SOON",
        "TASK_COMPLETED",
        "CONSULTATION_REQUESTED",
        "CONSULTATION_ACCEPTED",
        "CONSULTATION_REJECTED",
        "CONSULTATION_SCHEDULED",
        "CONSULTATION_CANCELLED",
        "CONSULTATION_COMPLETED",
        "PAYMENT_CREATED",
        "PAYMENT_SUCCEEDED",
        "PAYMENT_FAILED",
        "PAYMENT_REFUNDED",
        name="notificationtype",
    )
    notification_type_enum.drop(op.get_bind(), checkfirst=True)
