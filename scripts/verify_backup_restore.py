"""Database Backup & Disaster Recovery Verification Script.

Executes an automated end-to-end backup, checksum generation, restore to an isolated
target, and data integrity verification across all primary domain entities.
"""

import hashlib
import os
import sqlite3
import sys
import tempfile
import time


def compute_sha256(filepath: str) -> str:
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


def verify_backup_and_restore(source_db_path: str = "test.db") -> dict:
    if not os.path.exists(source_db_path):
        raise FileNotFoundError(f"Source database '{source_db_path}' does not exist.")

    start_time = time.perf_counter()
    print(f"[BACKUP-TEST] 1. Initiating live backup of '{source_db_path}'...")

    with tempfile.NamedTemporaryFile(suffix=".bak", delete=False) as backup_file:
        backup_path = backup_file.name

    with tempfile.NamedTemporaryFile(suffix=".restore.db", delete=False) as restore_file:
        restore_path = restore_file.name

    try:
        # 1. Execute safe atomic online backup
        src_conn = sqlite3.connect(source_db_path)
        dst_conn = sqlite3.connect(backup_path)
        with dst_conn:
            src_conn.backup(dst_conn, pages=100)
        dst_conn.close()

        backup_size = os.path.getsize(backup_path)
        backup_sha = compute_sha256(backup_path)
        print(f"[BACKUP-TEST]    -> Backup completed: {backup_size} bytes | SHA256: {backup_sha[:16]}...")

        # 2. Execute restore to clean isolated database
        print(f"[BACKUP-TEST] 2. Restoring backup to clean target '{restore_path}'...")
        bak_conn = sqlite3.connect(backup_path)
        restored_conn = sqlite3.connect(restore_path)
        with restored_conn:
            bak_conn.backup(restored_conn, pages=100)
        bak_conn.close()

        # 3. Data Integrity & Completeness Audit
        print("[BACKUP-TEST] 3. Running integrity checks and record audits...")

        # Check SQLite integrity check
        cur = restored_conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        integrity_status = cur.fetchone()[0]
        if integrity_status != "ok":
            raise ValueError(f"Restored database integrity check failed: {integrity_status}")

        # Check SQLite integrity check and foreign key consistency
        cur = restored_conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        integrity_status = cur.fetchone()[0]
        if integrity_status != "ok":
            raise ValueError(f"Restored database integrity check failed: {integrity_status}")

        cur.execute("PRAGMA foreign_key_check;")
        fk_violations = cur.fetchall()
        if fk_violations:
            raise ValueError(f"Restored database foreign key violations: {fk_violations}")

        # Dynamically enumerate ALL user tables from sqlite_master
        src_cur = src_conn.cursor()
        src_cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
        )
        all_tables = [row[0] for row in src_cur.fetchall()]

        # Compare schema definitions (DDL) for all tables and indexes
        src_cur.execute(
            "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name;"
        )
        src_schema = src_cur.fetchall()

        cur.execute(
            "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name;"
        )
        dst_schema = cur.fetchall()

        if src_schema != dst_schema:
            raise ValueError("Schema DDL mismatch between source and restored database!")

        table_counts = {}
        for table in all_tables:
            src_cur.execute(f"SELECT COUNT(*) FROM \"{table}\";")
            src_count = src_cur.fetchone()[0]

            cur.execute(f"SELECT COUNT(*) FROM \"{table}\";")
            dst_count = cur.fetchone()[0]

            if src_count != dst_count:
                raise ValueError(
                    f"Count mismatch for table '{table}': source has {src_count}, restored has {dst_count}"
                )
            table_counts[table] = src_count

        src_conn.close()
        restored_conn.close()

        duration = round(time.perf_counter() - start_time, 3)
        print(f"[BACKUP-TEST] 4. Verification successful! Restored and verified ALL {len(table_counts)} tables and schema objects in {duration}s.")

        return {
            "status": "PASSED",
            "source_db": source_db_path,
            "backup_size_bytes": backup_size,
            "backup_sha256": backup_sha,
            "integrity_check": integrity_status,
            "verified_tables": table_counts,
            "duration_seconds": duration,
        }

    finally:
        if os.path.exists(backup_path):
            os.remove(backup_path)
        if os.path.exists(restore_path):
            os.remove(restore_path)


if __name__ == "__main__":
    db_file = sys.argv[1] if len(sys.argv) > 1 else "test.db"
    res = verify_backup_and_restore(db_file)
    print("\n--- FINAL BACKUP & RESTORE VERIFICATION REPORT ---")
    for k, v in res.items():
        print(f"{k}: {v}")
