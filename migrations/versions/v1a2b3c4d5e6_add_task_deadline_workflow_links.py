"""add task deadline workflow links and blocked status

Revision ID: v1a2b3c4d5e6
Revises: u1a2b3c4d5e6
Create Date: 2026-09-06 16:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "v1a2b3c4d5e6"
down_revision: str | None = "u1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Update PostgreSQL enum if on postgresql
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'BLOCKED'")

    # 2. Add columns and indexes to case_tasks via batch_alter_table
    with op.batch_alter_table("case_tasks") as batch_op:
        batch_op.add_column(sa.Column("linked_evidence_id", sa.Uuid(), sa.ForeignKey("evidence.id", ondelete="SET NULL", name="fk_case_tasks_linked_evidence_id"), nullable=True))
        batch_op.add_column(sa.Column("linked_hearing_id", sa.Uuid(), sa.ForeignKey("case_hearings.id", ondelete="SET NULL", name="fk_case_tasks_linked_hearing_id"), nullable=True))
        batch_op.add_column(sa.Column("linked_deadline_id", sa.Uuid(), sa.ForeignKey("case_deadlines.id", ondelete="SET NULL", name="fk_case_tasks_linked_deadline_id"), nullable=True))
        batch_op.create_index("ix_case_tasks_linked_evidence_id", ["linked_evidence_id"])
        batch_op.create_index("ix_case_tasks_linked_hearing_id", ["linked_hearing_id"])
        batch_op.create_index("ix_case_tasks_linked_deadline_id", ["linked_deadline_id"])

    # 3. Add columns and indexes to case_deadlines via batch_alter_table
    with op.batch_alter_table("case_deadlines") as batch_op:
        batch_op.add_column(sa.Column("linked_hearing_id", sa.Uuid(), sa.ForeignKey("case_hearings.id", ondelete="SET NULL", name="fk_case_deadlines_linked_hearing_id"), nullable=True))
        batch_op.add_column(sa.Column("retrieval_method", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("confirmed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_case_deadlines_confirmed_by_user_id"), nullable=True))
        batch_op.create_index("ix_case_deadlines_linked_hearing_id", ["linked_hearing_id"])
        batch_op.create_index("ix_case_deadlines_confirmed_by_user_id", ["confirmed_by_user_id"])


def downgrade() -> None:
    with op.batch_alter_table("case_deadlines") as batch_op:
        batch_op.drop_index("ix_case_deadlines_confirmed_by_user_id")
        batch_op.drop_index("ix_case_deadlines_linked_hearing_id")
        batch_op.drop_column("confirmed_by_user_id")
        batch_op.drop_column("retrieved_at")
        batch_op.drop_column("retrieval_method")
        batch_op.drop_column("linked_hearing_id")

    with op.batch_alter_table("case_tasks") as batch_op:
        batch_op.drop_index("ix_case_tasks_linked_deadline_id")
        batch_op.drop_index("ix_case_tasks_linked_hearing_id")
        batch_op.drop_index("ix_case_tasks_linked_evidence_id")
        batch_op.drop_column("linked_deadline_id")
        batch_op.drop_column("linked_hearing_id")
        batch_op.drop_column("linked_evidence_id")
