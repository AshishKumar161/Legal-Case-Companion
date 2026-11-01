import os
import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alembic import command
from alembic.config import Config
import sqlalchemy as sa


def test_postgres_migration_lifecycle():
    pg_url = os.environ.get("TEST_POSTGRES_URL", "postgresql+psycopg2://postgres@127.0.0.1:5433/lcc_migration_test")
    try:
        # Check if Postgres is reachable via admin url
        admin_url = os.environ.get("TEST_POSTGRES_ADMIN_URL", "postgresql+psycopg2://postgres@127.0.0.1:5433/postgres")
        engine_check = sa.create_engine(admin_url, connect_args={"connect_timeout": 2})
        with engine_check.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
        engine_check.dispose()
    except Exception as e:
        print(f"SKIPPING PostgreSQL migration test (PostgreSQL not reachable: {e})")
        return

    print("\n=======================================================")
    print("=== PostgreSQL Production Database Migration Lifecycle ===")
    print("=======================================================")

    # Reset test database
    admin_engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(sa.text("DROP DATABASE IF EXISTS lcc_migration_test WITH (FORCE)"))
        conn.execute(sa.text("CREATE DATABASE lcc_migration_test"))
    admin_engine.dispose()

    os.environ["DATABASE_URL"] = pg_url
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", pg_url)

    print("--- Test PG-A: Clean Database Upgrade to Head ---")
    command.upgrade(alembic_cfg, "head")
    print("PASS: Upgraded clean PostgreSQL database to head successfully.")

    print("--- Test PG-B: Downgrade past 25500e9a54c3 to n1a2b3c4d5e6 ---")
    command.downgrade(alembic_cfg, "n1a2b3c4d5e6")
    print("PASS: Downgraded PostgreSQL database to n1a2b3c4d5e6 successfully.")

    engine = sa.create_engine(pg_url)
    with engine.connect() as conn:
        insp = sa.inspect(conn)
        tables = insp.get_table_names()
        assert "feedback" in tables, f"Expected feedback table after downgrade, got: {tables}"
        print("PASS: Verified feedback table was restored on downgrade.")

        print("--- Test PG-C: Insert parent user and legacy feedback row ---")
        conn.execute(sa.text("""
            INSERT INTO users (id, email, password_hash, role, account_status, created_at, updated_at)
            VALUES ('0191c000-0000-7000-8000-000000000002', 'testuser_pg@example.com', 'hash123', 'CLIENT', 'ACTIVE', now(), now())
            ON CONFLICT (id) DO NOTHING;
        """))
        conn.execute(sa.text("""
            INSERT INTO feedback (id, user_id, category, content, created_at, updated_at)
            VALUES ('0191c000-0000-7000-8000-000000000001', '0191c000-0000-7000-8000-000000000002',
                    'BUG', 'PostgreSQL legacy feedback test content', now(), now())
        """))
        conn.commit()
        print("PASS: Inserted legacy feedback record.")

    print("--- Test PG-D: Upgrade back to head with legacy data ---")
    command.upgrade(alembic_cfg, "head")
    print("PASS: Upgraded back to head with legacy data.")

    with engine.connect() as conn:
        insp = sa.inspect(conn)
        tables = insp.get_table_names()
        assert "pilot_feedback" in tables, "pilot_feedback must exist"
        assert "feedback" not in tables, "legacy feedback table should be dropped"

        res = conn.execute(sa.text("SELECT id, description, category, feedback_type FROM pilot_feedback WHERE id = '0191c000-0000-7000-8000-000000000001'")).first()
        assert res is not None, "Legacy feedback record was not preserved in pilot_feedback on PostgreSQL!"
        assert res[1] == "PostgreSQL legacy feedback test content", f"Content mismatch: {res[1]}"
        print(f"PASS: Verified legacy data preserved in pilot_feedback on PostgreSQL: {res}")

        # Verify key indices exist on head
        adv_indexes = {idx["name"] for idx in insp.get_indexes("advisor_sessions")}
        assert "ix_advisor_sessions_user_id" in adv_indexes, "Advisor sessions index missing!"
        print("PASS: Verified advisor_sessions index existence on PostgreSQL.")

    print("ALL POSTGRESQL MIGRATION LIFECYCLE TESTS PASSED!\n")


def run_migration_lifecycle_tests():
    # 1. Run on PostgreSQL
    test_postgres_migration_lifecycle()

    # 2. Run on SQLite
    print("=======================================================")
    print("=== SQLite Compatibility Migration Lifecycle ===")
    print("=======================================================")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        temp_db_path = tf.name

    try:
        temp_db_url = f"sqlite:///{temp_db_path}"
        os.environ["DATABASE_URL"] = temp_db_url

        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", temp_db_url)

        print("--- Test SQLite-A: Clean Database Upgrade to Head ---")
        command.upgrade(alembic_cfg, "head")
        print("PASS: Upgraded clean database to head successfully.")

        print("--- Test SQLite-B: Downgrade past 25500e9a54c3 to n1a2b3c4d5e6 ---")
        command.downgrade(alembic_cfg, "n1a2b3c4d5e6")
        print("PASS: Downgraded to n1a2b3c4d5e6 successfully.")

        engine = sa.create_engine(temp_db_url)
        with engine.connect() as conn:
            insp = sa.inspect(conn)
            tables = insp.get_table_names()
            assert "feedback" in tables, f"Expected feedback table after downgrade, got: {tables}"
            print("PASS: Verified feedback table was restored on downgrade.")

            print("--- Test SQLite-C: Insert legacy feedback row and upgrade ---")
            conn.execute(sa.text("""
                INSERT INTO feedback (id, user_id, category, content, created_at, updated_at)
                VALUES ('0191c000-0000-7000-8000-000000000001', '0191c000-0000-7000-8000-000000000002',
                        'BUG', 'Legacy feedback test content', '2026-09-01 10:00:00', '2026-09-01 10:00:00')
            """))
            conn.commit()

        print("--- Test SQLite-D: Upgrade back to head with legacy data ---")
        command.upgrade(alembic_cfg, "head")
        print("PASS: Upgraded back to head with legacy data.")

        with engine.connect() as conn:
            insp = sa.inspect(conn)
            tables = insp.get_table_names()
            assert "pilot_feedback" in tables, "pilot_feedback must exist"
            assert "feedback" not in tables, "legacy feedback table should be dropped"

            res = conn.execute(sa.text("SELECT id, description, category, feedback_type FROM pilot_feedback WHERE id = '0191c000-0000-7000-8000-000000000001'")).first()
            assert res is not None, "Legacy feedback record was not preserved in pilot_feedback!"
            assert res[1] == "Legacy feedback test content", f"Content mismatch: {res[1]}"
            print(f"PASS: Verified legacy data preserved in pilot_feedback: {res}")

        print("ALL SQLITE MIGRATION LIFECYCLE TESTS PASSED!\n")

    finally:
        if os.path.exists(temp_db_path):
            try:
                os.remove(temp_db_path)
            except Exception:
                pass


if __name__ == "__main__":
    run_migration_lifecycle_tests()
