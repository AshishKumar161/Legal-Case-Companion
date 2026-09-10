"""add_case_notes_and_task_fields

Revision ID: 3a8f1e2d4c5b
Revises: 29cdd9dc27a9
Create Date: 2026-08-30 01:25:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3a8f1e2d4c5b"
down_revision: str | None = "29cdd9dc27a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create case_notes table
    op.create_table(
        "case_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "is_private", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_case_notes_case_id"), "case_notes", ["case_id"], unique=False
    )
    op.create_index(
        op.f("ix_case_notes_author_user_id"),
        "case_notes",
        ["author_user_id"],
        unique=False,
    )

    # 2. Ensure taskpriority enum type exists in database
    task_priority_enum = sa.Enum("LOW", "MEDIUM", "HIGH", "URGENT", name="taskpriority")
    task_priority_enum.create(op.get_bind(), checkfirst=True)

    # 3. Add columns to case_tasks table
    with op.batch_alter_table("case_tasks") as batch_op:
        batch_op.add_column(
            sa.Column(
                "priority",
                task_priority_enum,
                server_default="MEDIUM",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("created_by_user_id", sa.Uuid(), nullable=True))
        batch_op.add_column(
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_index(
            op.f("ix_case_tasks_created_by_user_id"),
            ["created_by_user_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_case_tasks_created_by_user_id",
            "users",
            ["created_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("case_tasks") as batch_op:
        batch_op.drop_constraint("fk_case_tasks_created_by_user_id", type_="foreignkey")
        batch_op.drop_index(op.f("ix_case_tasks_created_by_user_id"))
        batch_op.drop_column("completed_at")
        batch_op.drop_column("created_by_user_id")
        batch_op.drop_column("priority")

    task_priority_enum = sa.Enum("LOW", "MEDIUM", "HIGH", "URGENT", name="taskpriority")
    task_priority_enum.drop(op.get_bind(), checkfirst=True)

    op.drop_index(op.f("ix_case_notes_author_user_id"), table_name="case_notes")
    op.drop_index(op.f("ix_case_notes_case_id"), table_name="case_notes")
    op.drop_table("case_notes")
