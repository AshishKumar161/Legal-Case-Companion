"""add court cases and user followed tables

Revision ID: o1a2b3c4d5e6
Revises: n1a2b3c4d5e6
Create Date: 2026-09-05 18:50:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "o1a2b3c4d5e6"
down_revision: str | None = "25500e9a54c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create court_cases table
    op.create_table(
        "court_cases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("cnr", sa.String(length=30), nullable=False),
        sa.Column("case_number", sa.String(length=100), nullable=False),
        sa.Column("case_type", sa.String(length=50), nullable=False),
        sa.Column("filing_number", sa.String(length=100), nullable=True),
        sa.Column("filing_date", sa.String(length=50), nullable=True),
        sa.Column("registration_date", sa.String(length=50), nullable=True),
        sa.Column("court_name", sa.String(length=255), nullable=False),
        sa.Column("bench", sa.String(length=255), nullable=True),
        sa.Column("court_room", sa.String(length=50), nullable=True),
        sa.Column("item_number", sa.String(length=50), nullable=True),
        sa.Column("petitioner", sa.String(length=255), nullable=False),
        sa.Column("petitioner_advocate", sa.String(length=255), nullable=True),
        sa.Column("respondent", sa.String(length=255), nullable=False),
        sa.Column("respondent_advocate", sa.String(length=255), nullable=True),
        sa.Column("acts_and_sections", sa.Text(), nullable=True),
        sa.Column("technical_status", sa.String(length=100), nullable=False),
        sa.Column("human_status", sa.Text(), nullable=False),
        sa.Column("next_hearing_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_hearing_purpose", sa.String(length=255), nullable=True),
        sa.Column("source_provenance", sa.String(length=100), server_default="OFFICIAL COURT DATA", nullable=False),
        sa.Column("last_synchronized_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("sync_status", sa.String(length=50), server_default="SYNCED", nullable=False),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id", ondelete="SET NULL"), nullable=True),
        sa.Column("history_json", sa.JSON(), nullable=True),
        sa.Column("cause_list_json", sa.JSON(), nullable=True),
        sa.Column("orders_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_court_cases_cnr", "court_cases", ["cnr"], unique=True)
    op.create_index("ix_court_cases_case_number", "court_cases", ["case_number"], unique=False)
    op.create_index("ix_court_cases_court_name", "court_cases", ["court_name"], unique=False)
    op.create_index("ix_court_cases_petitioner", "court_cases", ["petitioner"], unique=False)
    op.create_index("ix_court_cases_petitioner_advocate", "court_cases", ["petitioner_advocate"], unique=False)
    op.create_index("ix_court_cases_respondent", "court_cases", ["respondent"], unique=False)
    op.create_index("ix_court_cases_respondent_advocate", "court_cases", ["respondent_advocate"], unique=False)
    op.create_index("ix_court_cases_next_hearing_date", "court_cases", ["next_hearing_date"], unique=False)
    op.create_index("ix_court_cases_case_id", "court_cases", ["case_id"], unique=False)

    # 2. Create user_followed_cases table
    op.create_table(
        "user_followed_cases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("court_case_id", sa.Uuid(), sa.ForeignKey("court_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.UniqueConstraint("user_id", "court_case_id", name="uq_user_followed_cases_user_court_case"),
    )

    op.create_index("ix_user_followed_cases_user_id", "user_followed_cases", ["user_id"], unique=False)
    op.create_index("ix_user_followed_cases_court_case_id", "user_followed_cases", ["court_case_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_followed_cases_court_case_id", table_name="user_followed_cases")
    op.drop_index("ix_user_followed_cases_user_id", table_name="user_followed_cases")
    op.drop_table("user_followed_cases")

    op.drop_index("ix_court_cases_case_id", table_name="court_cases")
    op.drop_index("ix_court_cases_next_hearing_date", table_name="court_cases")
    op.drop_index("ix_court_cases_respondent_advocate", table_name="court_cases")
    op.drop_index("ix_court_cases_respondent", table_name="court_cases")
    op.drop_index("ix_court_cases_petitioner_advocate", table_name="court_cases")
    op.drop_index("ix_court_cases_petitioner", table_name="court_cases")
    op.drop_index("ix_court_cases_court_name", table_name="court_cases")
    op.drop_index("ix_court_cases_case_number", table_name="court_cases")
    op.drop_index("ix_court_cases_cnr", table_name="court_cases")
    op.drop_table("court_cases")
