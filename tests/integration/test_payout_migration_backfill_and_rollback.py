import os
import uuid
import pytest
from sqlalchemy import create_engine, text
from alembic.config import Config
from alembic import command

PG_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres@127.0.0.1:5433/lcc_migration_test",
)

pytestmark = pytest.mark.skipif(
    not PG_URL.startswith("postgresql"),
    reason="PostgreSQL integration environment required for migration testing",
)


def test_payout_migration_backfill_and_rollback_on_populated_postgresql():
    """
    1. Populate advocate_payouts with legacy records containing NULL and duplicate idempotency keys.
    2. Run alembic upgrade to z3a4b5c6d7e8.
    3. Verify all records have non-null, unique idempotency keys.
    4. Verify database schema has nullable=False.
    5. Verify duplicate insertion is blocked by uniqueness constraint.
    6. Rollback to z2a3b4c5d6e7 and verify column returns to nullable=True.
    7. Re-upgrade to head to leave the database clean.
    """
    engine = create_engine(PG_URL)
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", PG_URL)

    with engine.begin() as conn:
        res = conn.execute(text("SELECT version_num FROM alembic_version;")).scalar()
    
    # 1. Downgrade to z2a3b4c5d6e7 so advocate_payouts.idempotency_key allows NULL and duplicates
    command.downgrade(alembic_cfg, "z2a3b4c5d6e7")

    with engine.begin() as conn:
        lawyer_id = str(uuid.uuid4())
        conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, role, account_status, created_at, updated_at) "
                "VALUES (:id, :email, 'hash', 'LAWYER', 'ACTIVE', NOW(), NOW()) "
                "ON CONFLICT DO NOTHING;"
            ),
            {"id": lawyer_id, "email": f"lawyer_{lawyer_id[:8]}@example.com"}
        )

        # Drop unique index temporarily to simulate historical unindexed/duplicate legacy state
        conn.execute(text("DROP INDEX IF EXISTS ix_advocate_payouts_idempotency_key;"))

        # Insert 4 historical records:
        # - Row 1: NULL idempotency_key
        # - Row 2: empty string idempotency_key
        # - Row 3: duplicate key 'legacy_dup_key'
        # - Row 4: duplicate key 'legacy_dup_key'
        id1 = str(uuid.uuid4())
        id2 = str(uuid.uuid4())
        id3 = str(uuid.uuid4())
        id4 = str(uuid.uuid4())

        for pid, key, payout_id in [
            (id1, None, f"pout_test_{id1[:6]}"),
            (id2, "", f"pout_test_{id2[:6]}"),
            (id3, "legacy_dup_key", f"pout_test_{id3[:6]}"),
            (id4, "legacy_dup_key", f"pout_test_{id4[:6]}"),
        ]:
            conn.execute(
                text(
                    "INSERT INTO advocate_payouts (id, payout_id, advocate_user_id, amount, currency, status, provider, metadata, idempotency_key, created_at, updated_at) "
                    "VALUES (:id, :payout_id, :uid, 5000.00, 'INR', 'COMPLETED', 'STRIPE', '{}', :key, NOW(), NOW());"
                ),
                {"id": pid, "payout_id": payout_id, "uid": lawyer_id, "key": key}
            )

    # 2. Run the upgrade migration to z3a4b5c6d7e8
    command.upgrade(alembic_cfg, "z3a4b5c6d7e8")

    # Re-create unique index on idempotency_key if it was dropped for the test
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_advocate_payouts_idempotency_key ON advocate_payouts (idempotency_key);"
            )
        )

    # 3. Verify backfill on PostgreSQL
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT id, idempotency_key FROM advocate_payouts WHERE id IN (:id1, :id2, :id3, :id4);"
            ),
            {"id1": id1, "id2": id2, "id3": id3, "id4": id4}
        ).fetchall()

        keys = {r[0]: r[1] for r in rows}
        
        # Row 1 (was NULL): backfilled with 'pout_legacy_' || id
        assert keys[uuid.UUID(id1)] == f"pout_legacy_{id1}"
        # Row 2 (was empty): backfilled with 'pout_legacy_' || id
        assert keys[uuid.UUID(id2)] == f"pout_legacy_{id2}"
        # Row 3 & 4 (were duplicate 'legacy_dup_key'):
        key3 = keys[uuid.UUID(id3)]
        key4 = keys[uuid.UUID(id4)]
        assert key3 != key4, "Duplicate keys must be deduplicated"
        assert "legacy_dup_key" in key3 and "legacy_dup_key" in key4

        # Verify no NULLs anywhere in the table
        null_count = conn.execute(
            text("SELECT COUNT(*) FROM advocate_payouts WHERE idempotency_key IS NULL OR idempotency_key = '';")
        ).scalar()
        assert null_count == 0

        # Verify column metadata: is_nullable is NO in information_schema
        is_nullable = conn.execute(
            text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'advocate_payouts' AND column_name = 'idempotency_key';"
            )
        ).scalar()
        assert is_nullable == "NO", f"Expected is_nullable to be 'NO', got '{is_nullable}'"

        # Verify uniqueness blocks new duplicates
        with pytest.raises(Exception):
            conn.execute(
                text(
                    "INSERT INTO advocate_payouts (id, payout_id, advocate_user_id, amount, currency, status, provider, metadata, idempotency_key, created_at, updated_at) "
                    "VALUES (:id, 'pout_fail_dup', :uid, 1000.00, 'INR', 'COMPLETED', 'STRIPE', '{}', :key, NOW(), NOW());"
                ),
                {"id": str(uuid.uuid4()), "uid": lawyer_id, "key": keys[uuid.UUID(id1)]}
            )

    # 4. Verify Rollback (downgrade to z2a3b4c5d6e7)
    command.downgrade(alembic_cfg, "z2a3b4c5d6e7")

    with engine.begin() as conn:
        is_nullable_after_rollback = conn.execute(
            text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'advocate_payouts' AND column_name = 'idempotency_key';"
            )
        ).scalar()
        assert is_nullable_after_rollback == "YES", "Expected column to be nullable after downgrade"

    # 5. Clean up: Upgrade back to head
    command.upgrade(alembic_cfg, "head")

    with engine.begin() as conn:
        is_nullable_head = conn.execute(
            text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'advocate_payouts' AND column_name = 'idempotency_key';"
            )
        ).scalar()
        assert is_nullable_head == "NO"

        # Clean test records
        conn.execute(
            text("DELETE FROM advocate_payouts WHERE id IN (:id1, :id2, :id3, :id4);"),
            {"id1": id1, "id2": id2, "id3": id3, "id4": id4}
        )
