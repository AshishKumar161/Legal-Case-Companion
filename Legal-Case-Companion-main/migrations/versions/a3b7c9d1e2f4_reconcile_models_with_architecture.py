"""Reconcile models with architecture: enum fix, participant columns, indexes, constraints

Revision ID: a3b7c9d1e2f4
Revises: 2c8f208c74a0
Create Date: 2026-08-22 17:45:00.000000

Phase 2: Fix DocumentSecurityStatus enum, add CaseParticipant columns
Phase 3: Add updated_at trigger
Phase 13: Add indexes and CHECK constraints
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3b7c9d1e2f4"
down_revision: str | None = "2c8f208c74a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # Phase 2: Reconcile DocumentSecurityStatus enum
    if is_postgres:
        op.execute(
            "ALTER TYPE documentsecuritystatus ADD VALUE IF NOT EXISTS 'PENDING'"
        )
        op.execute(
            "ALTER TYPE documentsecuritystatus ADD VALUE IF NOT EXISTS 'APPROVED'"
        )

    # ---------------------------------------------------------------
    # Phase 2: Add joined_at and ended_at to case_participants
    # ---------------------------------------------------------------
    op.add_column(
        "case_participants",
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    )
    op.add_column(
        "case_participants",
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ---------------------------------------------------------------
    # Phase 3: Create PostgreSQL trigger for updated_at
    # ---------------------------------------------------------------
    if is_postgres:
        op.execute("""
            CREATE OR REPLACE FUNCTION set_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)

        tables_with_updated_at = [
            "users",
            "client_profiles",
            "lawyer_profiles",
            "cases",
            "case_participants",
            "case_timeline_events",
            "documents",
            "consultations",
            "payments",
            "lawyer_verifications",
        ]
        for table in tables_with_updated_at:
            trigger_name = f"trg_{table}_updated_at"
            op.execute(f"""
                CREATE TRIGGER {trigger_name}
                BEFORE UPDATE ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION set_updated_at();
            """)

    # ---------------------------------------------------------------
    # Phase 13: Add indexes per 02_DATABASE_DESIGN.md §9
    # ---------------------------------------------------------------
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_phone", "users", ["phone"])
    op.create_index("ix_client_profiles_user_id", "client_profiles", ["user_id"])
    op.create_index("ix_lawyer_profiles_user_id", "lawyer_profiles", ["user_id"])
    op.create_index("ix_case_participants_user_id", "case_participants", ["user_id"])
    op.create_index("ix_case_participants_case_id", "case_participants", ["case_id"])
    op.create_index("ix_documents_case_id", "documents", ["case_id"])
    op.create_index("ix_documents_uploaded_by", "documents", ["uploaded_by"])
    op.create_index("ix_consultations_client_id", "consultations", ["client_id"])
    op.create_index("ix_consultations_lawyer_id", "consultations", ["lawyer_id"])
    op.create_index("ix_payments_payer_user_id", "payments", ["payer_user_id"])
    op.create_index(
        "ix_refresh_token_sessions_token_family_id",
        "refresh_token_sessions",
        ["token_family_id"],
    )
    op.create_index(
        "ix_refresh_token_sessions_user_id", "refresh_token_sessions", ["user_id"]
    )
    op.create_index(
        "ix_refresh_token_sessions_token_hash", "refresh_token_sessions", ["token_hash"]
    )
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_events_entity_id", "audit_events", ["entity_id"])
    op.create_index("ix_audit_events_timestamp", "audit_events", ["timestamp"])
    op.create_index(
        "ix_case_timeline_events_case_id", "case_timeline_events", ["case_id"]
    )

    # ---------------------------------------------------------------
    # Phase 13: CHECK constraints
    # ---------------------------------------------------------------
    if is_postgres:
        op.execute(
            "ALTER TABLE documents ADD CONSTRAINT ck_documents_file_size_positive CHECK (file_size > 0)"
        )
        op.execute(
            "ALTER TABLE documents ADD CONSTRAINT ck_documents_file_size_max CHECK (file_size <= 10485760)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute(
            "ALTER TABLE documents DROP CONSTRAINT IF EXISTS ck_documents_file_size_max"
        )
        op.execute(
            "ALTER TABLE documents DROP CONSTRAINT IF EXISTS ck_documents_file_size_positive"
        )

    op.drop_index("ix_case_timeline_events_case_id")
    op.drop_index("ix_audit_events_timestamp")
    op.drop_index("ix_audit_events_entity_id")
    op.drop_index("ix_audit_events_actor_user_id")
    op.drop_index("ix_refresh_token_sessions_token_hash")
    op.drop_index("ix_refresh_token_sessions_user_id")
    op.drop_index("ix_refresh_token_sessions_token_family_id")
    op.drop_index("ix_payments_payer_user_id")
    op.drop_index("ix_consultations_lawyer_id")
    op.drop_index("ix_consultations_client_id")
    op.drop_index("ix_documents_uploaded_by")
    op.drop_index("ix_documents_case_id")
    op.drop_index("ix_case_participants_case_id")
    op.drop_index("ix_case_participants_user_id")
    op.drop_index("ix_lawyer_profiles_user_id")
    op.drop_index("ix_client_profiles_user_id")
    op.drop_index("ix_users_phone")
    op.drop_index("ix_users_email")

    if is_postgres:
        tables_with_updated_at = [
            "users",
            "client_profiles",
            "lawyer_profiles",
            "cases",
            "case_participants",
            "case_timeline_events",
            "documents",
            "consultations",
            "payments",
            "lawyer_verifications",
        ]
        for table in tables_with_updated_at:
            trigger_name = f"trg_{table}_updated_at"
            op.execute(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table}")
        op.execute("DROP FUNCTION IF EXISTS set_updated_at()")

    op.drop_column("case_participants", "ended_at")
    op.drop_column("case_participants", "joined_at")

    if is_postgres:
        # PENDING and APPROVED cannot easily be removed from an enum type in Postgres without recreation
        pass
