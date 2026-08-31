"""Recreate document enum

Revision ID: b4c8d0e1f3g5
Revises: a3b7c9d1e2f4
Create Date: 2026-08-22 18:24:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4c8d0e1f3g5"
down_revision: str | None = "a3b7c9d1e2f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        # 1. Update any existing data to use the canonical state
        op.execute("COMMIT")
        op.execute(
            "UPDATE documents SET security_status = 'SAFE' WHERE security_status = 'APPROVED'"
        )

        # 2. Rename the old type
        op.execute(
            "ALTER TYPE documentsecuritystatus RENAME TO documentsecuritystatus_old"
        )

        # 3. Create the new type with the EXACT canonical states
        op.execute(
            "CREATE TYPE documentsecuritystatus AS ENUM('PENDING', 'QUARANTINED', 'VALIDATING', 'SCANNING', 'SAFE', 'REJECTED')"
        )

        # 4. Alter the column to use the new type
        op.execute(
            "ALTER TABLE documents ALTER COLUMN security_status TYPE documentsecuritystatus USING security_status::text::documentsecuritystatus"
        )

        # 5. Drop the old type
        op.execute("DROP TYPE documentsecuritystatus_old")


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        # Revert enum to old state
        op.execute(
            "ALTER TYPE documentsecuritystatus RENAME TO documentsecuritystatus_new"
        )
        op.execute(
            "CREATE TYPE documentsecuritystatus AS ENUM('QUARANTINED', 'VALIDATING', 'SCANNING', 'SAFE', 'REJECTED', 'PENDING', 'APPROVED')"
        )
        # Map SAFE back to APPROVED during downgrade to ensure data fits the old enum
        op.execute(
            "UPDATE documents SET security_status = 'APPROVED' WHERE security_status = 'SAFE'"
        )
        op.execute(
            "ALTER TABLE documents ALTER COLUMN security_status TYPE documentsecuritystatus USING security_status::text::documentsecuritystatus"
        )
        op.execute("DROP TYPE documentsecuritystatus_new")
