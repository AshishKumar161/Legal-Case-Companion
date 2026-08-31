"""Add CaseNote visibility enum and indexes

Revision ID: 9b8a7c6d5e4f
Revises: 7a8b9c0d1e2f
Create Date: 2026-08-30

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "9b8a7c6d5e4f"
down_revision: str | None = "7f8a9b0c1d2e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

casenotevisibility_enum = postgresql.ENUM(
    "CLIENT_PRIVATE", "LAWYER_PRIVATE", "SHARED", name="casenotevisibility", create_type=False
)


def upgrade() -> None:
    # 1. Create Enum in PostgreSQL if applicable
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        casenotevisibility_enum.create(bind, checkfirst=True)

    # 2. Add visibility column to case_notes
    op.add_column(
        "case_notes",
        sa.Column(
            "visibility",
            sa.Enum("CLIENT_PRIVATE", "LAWYER_PRIVATE", "SHARED", name="casenotevisibility"),
            server_default="SHARED",
            nullable=False,
        ),
    )

    # 3. Migrate existing notes where is_private is True
    # For lawyer authors, set to LAWYER_PRIVATE; for clients, set to CLIENT_PRIVATE
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            UPDATE case_notes
            SET visibility = 'LAWYER_PRIVATE'::casenotevisibility
            FROM users
            WHERE case_notes.author_user_id = users.id
              AND case_notes.is_private = TRUE
              AND users.role = 'LAWYER'
            """
        )
        op.execute(
            """
            UPDATE case_notes
            SET visibility = 'CLIENT_PRIVATE'::casenotevisibility
            FROM users
            WHERE case_notes.author_user_id = users.id
              AND case_notes.is_private = TRUE
              AND users.role != 'LAWYER'
            """
        )
    else:
        op.execute(
            """
            UPDATE case_notes
            SET visibility = 'LAWYER_PRIVATE'
            WHERE is_private = 1
              AND author_user_id IN (SELECT id FROM users WHERE role = 'LAWYER')
            """
        )
        op.execute(
            """
            UPDATE case_notes
            SET visibility = 'CLIENT_PRIVATE'
            WHERE is_private = 1
              AND author_user_id NOT IN (SELECT id FROM users WHERE role = 'LAWYER')
            """
        )

    # 4. Create Indexes
    op.create_index(
        "ix_case_notes_visibility",
        "case_notes",
        ["visibility"],
    )
    op.create_index(
        "ix_case_notes_case_visibility",
        "case_notes",
        ["case_id", "visibility"],
    )


def downgrade() -> None:
    op.drop_index("ix_case_notes_case_visibility", table_name="case_notes")
    op.drop_index("ix_case_notes_visibility", table_name="case_notes")
    op.drop_column("case_notes", "visibility")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        casenotevisibility_enum.drop(bind, checkfirst=True)
