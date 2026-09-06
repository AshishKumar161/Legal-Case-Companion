"""add phase 10.4 maintenance job types

Revision ID: s1a2b3c4d5e6
Revises: r1a2b3c4d5e6
Create Date: 2026-09-06 12:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "s1a2b3c4d5e6"
down_revision: str | None = "r1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE jobtype ADD VALUE IF NOT EXISTS 'STALE_MEETING_CLEANUP'")
        op.execute("ALTER TYPE jobtype ADD VALUE IF NOT EXISTS 'RECORDING_UPLOAD_RETRY'")
        op.execute("ALTER TYPE jobtype ADD VALUE IF NOT EXISTS 'WEBHOOK_REPROCESS'")
        op.execute("ALTER TYPE jobtype ADD VALUE IF NOT EXISTS 'COMMERCIAL_RECONCILIATION'")
        op.execute("ALTER TYPE jobtype ADD VALUE IF NOT EXISTS 'EXPIRED_SESSION_CLEANUP'")
        op.execute("ALTER TYPE jobtype ADD VALUE IF NOT EXISTS 'NOTIFICATION_RETRY'")


def downgrade() -> None:
    # In PostgreSQL, removing values from an enum type is not directly supported without recreating the type.
    # Leaving as no-op to maintain forward compatibility.
    pass
