"""add payout idempotency and distributed locks

Revision ID: y1a2b3c4d5e6
Revises: 8b5b923063b9
Create Date: 2026-11-02 02:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'y1a2b3c4d5e6'
down_revision: Union[str, None] = '8b5b923063b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _safe_create_index(index_name: str, table_name: str, columns: list[str], unique: bool = False, where: str = None) -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table(table_name):
        return
    existing_indexes = {ix['name'] for ix in insp.get_indexes(table_name)}
    if index_name not in existing_indexes:
        kwargs = {"unique": unique}
        if where:
            kwargs["postgresql_where"] = sa.text(where)
            kwargs["sqlite_where"] = sa.text(where)
        op.create_index(index_name, table_name, columns, **kwargs)


def _safe_drop_index(index_name: str, table_name: str) -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table(table_name):
        existing_indexes = {ix['name'] for ix in insp.get_indexes(table_name)}
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("advocate_payouts"):
        columns = {col["name"] for col in insp.get_columns("advocate_payouts")}
        if "idempotency_key" not in columns:
            op.add_column("advocate_payouts", sa.Column("idempotency_key", sa.String(length=255), nullable=True))
        _safe_create_index(
            "ix_advocate_payouts_idempotency_key",
            "advocate_payouts",
            ["idempotency_key"],
            unique=True,
        )
        _safe_create_index(
            "uq_advocate_payout_active_commercial_txn",
            "advocate_payouts",
            ["commercial_transaction_id"],
            unique=True,
            where="commercial_transaction_id IS NOT NULL AND status IN ('PENDING', 'PAID')",
        )


def downgrade() -> None:
    _safe_drop_index("uq_advocate_payout_active_commercial_txn", table_name="advocate_payouts")
    _safe_drop_index("ix_advocate_payouts_idempotency_key", table_name="advocate_payouts")
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("advocate_payouts"):
        columns = {col["name"] for col in insp.get_columns("advocate_payouts")}
        if "idempotency_key" in columns:
            with op.batch_alter_table("advocate_payouts") as batch_op:
                batch_op.drop_column("idempotency_key")
