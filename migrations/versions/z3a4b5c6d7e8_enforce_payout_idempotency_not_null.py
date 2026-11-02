"""enforce advocate payout idempotency not null

Revision ID: z3a4b5c6d7e8
Revises: z2a3b4c5d6e7
Create Date: 2026-11-02 08:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'z3a4b5c6d7e8'
down_revision = 'z2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table("advocate_payouts"):
        # 1. Deduplicate any duplicate idempotency keys in legacy data
        if bind.dialect.name == "postgresql":
            op.execute(
                sa.text(
                    """
                    WITH ranked AS (
                        SELECT id, idempotency_key,
                               ROW_NUMBER() OVER (PARTITION BY idempotency_key ORDER BY created_at ASC, id ASC) as rnk
                        FROM advocate_payouts
                        WHERE idempotency_key IS NOT NULL AND idempotency_key != ''
                    )
                    UPDATE advocate_payouts ap
                    SET idempotency_key = ap.idempotency_key || '_dup_' || SUBSTRING(ap.id::text, 1, 8)
                    FROM ranked
                    WHERE ap.id = ranked.id AND ranked.rnk > 1;
                    """
                )
            )
        else:
            # SQLite fallback deduplication
            op.execute(
                sa.text(
                    """
                    UPDATE advocate_payouts
                    SET idempotency_key = idempotency_key || '_dup_' || SUBSTR(id, 1, 8)
                    WHERE id IN (
                        SELECT a1.id
                        FROM advocate_payouts a1
                        JOIN advocate_payouts a2 ON a1.idempotency_key = a2.idempotency_key AND a1.id > a2.id
                        WHERE a1.idempotency_key IS NOT NULL AND a1.idempotency_key != ''
                    );
                    """
                )
            )

        # 2. Backfill any null or empty idempotency keys with deterministic fallback
        op.execute(
            sa.text(
                "UPDATE advocate_payouts SET idempotency_key = 'pout_legacy_' || id "
                "WHERE idempotency_key IS NULL OR idempotency_key = '';"
            )
        )
        if bind.dialect.name == "postgresql":
            op.alter_column("advocate_payouts", "idempotency_key", nullable=False)
        else:
            with op.batch_alter_table("advocate_payouts") as batch_op:
                batch_op.alter_column("idempotency_key", nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("advocate_payouts"):
        if bind.dialect.name == "postgresql":
            op.alter_column("advocate_payouts", "idempotency_key", nullable=True)
        else:
            with op.batch_alter_table("advocate_payouts") as batch_op:
                batch_op.alter_column("idempotency_key", nullable=True)
