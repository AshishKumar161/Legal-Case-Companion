"""add outbox events and reliability enhancements

Revision ID: i1a2b3c4d5e6
Revises: h1a2b3c4d5e6
Create Date: 2026-09-04 02:26:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i1a2b3c4d5e6"
down_revision: str | None = "h1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add new enum values to jobstatus and jobtype for postgres
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE jobstatus ADD VALUE IF NOT EXISTS 'DEAD_LETTER'")
        op.execute("ALTER TYPE jobtype ADD VALUE IF NOT EXISTS 'EVIDENCE_SCAN_AND_ACTIVATE'")
        op.execute("ALTER TYPE jobtype ADD VALUE IF NOT EXISTS 'EVIDENCE_INTEGRITY_AUDIT'")
        op.execute("ALTER TYPE jobtype ADD VALUE IF NOT EXISTS 'EVIDENCE_ORPHAN_RECONCILIATION'")
        op.execute("ALTER TYPE jobtype ADD VALUE IF NOT EXISTS 'ABANDONED_UPLOAD_CLEANUP'")
        op.execute("ALTER TYPE jobtype ADD VALUE IF NOT EXISTS 'OUTBOX_DISPATCH'")

    # 2. Create outbox_events table
    outbox_status_enum = sa.Enum(
        "PENDING",
        "PROCESSING",
        "PUBLISHED",
        "FAILED",
        "DEAD_LETTER",
        name="outboxstatus",
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", sa.UUID(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("headers", sa.JSON(), nullable=False),
        sa.Column("status", outbox_status_enum, nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("error_category", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(op.f("ix_outbox_events_event_type"), "outbox_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_outbox_events_aggregate_type"), "outbox_events", ["aggregate_type"], unique=False)
    op.create_index(op.f("ix_outbox_events_aggregate_id"), "outbox_events", ["aggregate_id"], unique=False)
    op.create_index(op.f("ix_outbox_events_status"), "outbox_events", ["status"], unique=False)
    op.create_index(op.f("ix_outbox_events_scheduled_at"), "outbox_events", ["scheduled_at"], unique=False)
    op.create_index(
        "ix_outbox_events_status_scheduled",
        "outbox_events",
        ["status", "scheduled_at"],
        unique=False,
    )
    op.create_index(
        "ix_outbox_events_aggregate",
        "outbox_events",
        ["aggregate_type", "aggregate_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_events_aggregate", table_name="outbox_events")
    op.drop_index("ix_outbox_events_status_scheduled", table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_scheduled_at"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_status"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_aggregate_id"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_aggregate_type"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_event_type"), table_name="outbox_events")
    op.drop_table("outbox_events")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS outboxstatus")
