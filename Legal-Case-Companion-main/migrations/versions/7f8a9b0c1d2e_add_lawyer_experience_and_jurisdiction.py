"""Add lawyer experience, jurisdiction and consultation scheduling index

Revision ID: 7f8a9b0c1d2e
Revises: 5c8a1b2e3f4d
Create Date: 2026-08-30

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7f8a9b0c1d2e"
down_revision: str | None = "5c8a1b2e3f4d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add experience_years and court_jurisdictions to lawyer_profiles
    op.add_column(
        "lawyer_profiles",
        sa.Column("experience_years", sa.Integer(), nullable=True),
    )
    op.add_column(
        "lawyer_profiles",
        sa.Column("court_jurisdictions", sa.JSON(), nullable=True),
    )

    # 2. Add indexes for efficient search and scheduling lookups
    op.create_index(
        "ix_lawyer_profiles_location",
        "lawyer_profiles",
        ["location"],
    )
    op.create_index(
        "ix_consultations_lawyer_scheduled",
        "consultations",
        ["lawyer_id", "scheduled_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_consultations_lawyer_scheduled", table_name="consultations")
    op.drop_index("ix_lawyer_profiles_location", table_name="lawyer_profiles")
    op.drop_column("lawyer_profiles", "court_jurisdictions")
    op.drop_column("lawyer_profiles", "experience_years")
