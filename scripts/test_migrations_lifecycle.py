import os
import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alembic import command
from alembic.config import Config
import sqlalchemy as sa


def run_migration_lifecycle_tests():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        temp_db_path = tf.name

    try:
        temp_db_url = f"sqlite:///{temp_db_path}"
        os.environ["DATABASE_URL"] = temp_db_url

        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", temp_db_url)

        print("--- Test A: Clean Database Upgrade to Head ---")
        command.upgrade(alembic_cfg, "head")
        print("PASS: Upgraded clean database to head successfully.")

        print("--- Test B: Downgrade past 25500e9a54c3 to n1a2b3c4d5e6 ---")
        command.downgrade(alembic_cfg, "n1a2b3c4d5e6")
        print("PASS: Downgraded to n1a2b3c4d5e6 successfully.")

        engine = sa.create_engine(temp_db_url)
        with engine.connect() as conn:
            insp = sa.inspect(conn)
            tables = insp.get_table_names()
            assert "feedback" in tables, f"Expected feedback table after downgrade, got: {tables}"
            print("PASS: Verified feedback table was restored on downgrade.")

            print("--- Test C: Insert legacy feedback row and upgrade ---")
            conn.execute(sa.text("""
                INSERT INTO feedback (id, user_id, category, content, created_at, updated_at)
                VALUES ('0191c000-0000-7000-8000-000000000001', '0191c000-0000-7000-8000-000000000002',
                        'BUG', 'Legacy feedback test content', '2026-09-01 10:00:00', '2026-09-01 10:00:00')
            """))
            conn.commit()

        print("--- Test D: Upgrade back to head with legacy data ---")
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

        print("ALL MIGRATION LIFECYCLE TESTS PASSED!")

    finally:
        if os.path.exists(temp_db_path):
            try:
                os.remove(temp_db_path)
            except Exception:
                pass


if __name__ == "__main__":
    run_migration_lifecycle_tests()
