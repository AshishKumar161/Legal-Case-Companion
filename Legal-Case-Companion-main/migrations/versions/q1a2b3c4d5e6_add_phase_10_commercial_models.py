"""add phase 10 commercial models and support messages

Revision ID: q1a2b3c4d5e6
Revises: p1a2b3c4d5e6
Create Date: 2026-09-05 20:15:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "q1a2b3c4d5e6"
down_revision: str | None = "p1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. support_case_messages table
    op.create_table(
        "support_case_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("support_case_id", sa.Uuid(), sa.ForeignKey("support_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sender_role", sa.String(50), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("is_internal_note", sa.Boolean(), default=False, nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), onupdate=sa.func.current_timestamp(), nullable=False),
    )
    op.create_index("ix_support_case_messages_case_id", "support_case_messages", ["support_case_id"])
    op.create_index("ix_support_case_messages_sender_id", "support_case_messages", ["sender_user_id"])

    # 2. advocate_payouts table
    op.create_table(
        "advocate_payouts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("payout_id", sa.String(100), unique=True, nullable=False),
        sa.Column("advocate_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("commercial_transaction_id", sa.Uuid(), sa.ForeignKey("commercial_transactions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(10), default="INR", nullable=False),
        sa.Column("status", sa.String(50), default="PENDING", nullable=False),
        sa.Column("provider", sa.String(50), default="RAZORPAYX", nullable=False),
        sa.Column("provider_payout_id", sa.String(255), unique=True, nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("audit_notes", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), onupdate=sa.func.current_timestamp(), nullable=False),
    )
    op.create_index("ix_advocate_payouts_payout_id", "advocate_payouts", ["payout_id"])
    op.create_index("ix_advocate_payouts_advocate_user_id", "advocate_payouts", ["advocate_user_id"])
    op.create_index("ix_advocate_payouts_status", "advocate_payouts", ["status"])

    # 3. refund_records table
    op.create_table(
        "refund_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("refund_id", sa.String(100), unique=True, nullable=False),
        sa.Column("commercial_transaction_id", sa.Uuid(), sa.ForeignKey("commercial_transactions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(10), default="INR", nullable=False),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), default="PENDING", nullable=False),
        sa.Column("processed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("gateway_refund_id", sa.String(255), unique=True, nullable=True),
        sa.Column("audit_notes", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), onupdate=sa.func.current_timestamp(), nullable=False),
    )
    op.create_index("ix_refund_records_refund_id", "refund_records", ["refund_id"])
    op.create_index("ix_refund_records_tx_id", "refund_records", ["commercial_transaction_id"])
    op.create_index("ix_refund_records_status", "refund_records", ["status"])


def downgrade() -> None:
    op.drop_index("ix_refund_records_status", table_name="refund_records")
    op.drop_index("ix_refund_records_tx_id", table_name="refund_records")
    op.drop_index("ix_refund_records_refund_id", table_name="refund_records")
    op.drop_table("refund_records")

    op.drop_index("ix_advocate_payouts_status", table_name="advocate_payouts")
    op.drop_index("ix_advocate_payouts_advocate_user_id", table_name="advocate_payouts")
    op.drop_index("ix_advocate_payouts_payout_id", table_name="advocate_payouts")
    op.drop_table("advocate_payouts")

    op.drop_index("ix_support_case_messages_sender_id", table_name="support_case_messages")
    op.drop_index("ix_support_case_messages_case_id", table_name="support_case_messages")
    op.drop_table("support_case_messages")
