"""Utility script to inspect tables and data inside test.db.
Run with:
    .\\.venv\\Scripts\\python scripts/inspect_db.py
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test.db")

def main():
    if not os.path.exists(DB_PATH):
        print(f"Database file not found at: {DB_PATH}")
        return

    print("=" * 70)
    print(f"Database File: {DB_PATH}")
    print(f"Size: {os.path.getsize(DB_PATH) / 1024:.2f} KB")
    print("=" * 70)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. List all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [row[0] for row in cursor.fetchall()]
    print("\nTables in database:")
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM \"{t}\"")
        count = cursor.fetchone()[0]
        print(f"  - {t:<30} ({count} rows)")

    # 2. Show users table
    print("\n" + "=" * 70)
    print("RECENT USERS IN 'users' TABLE:")
    print("=" * 70)
    cursor.execute("SELECT id, email, role, account_status, created_at FROM users ORDER BY created_at DESC LIMIT 10;")
    rows = cursor.fetchall()
    if not rows:
        print("  (No users registered yet)")
    else:
        for r in rows:
            print(f"  Email:   {r[1]}")
            print(f"  User ID: {r[0]}")
            print(f"  Role:    {r[2]} | Status: {r[3]} | Created: {r[4]}")
            print("  " + "-" * 50)

    # 3. Show recent verification tokens
    print("\n" + "=" * 70)
    print("RECENT EMAIL VERIFICATION TOKENS:")
    print("=" * 70)
    cursor.execute("SELECT user_id, email, used_at, created_at FROM email_verification_tokens ORDER BY created_at DESC LIMIT 5;")
    token_rows = cursor.fetchall()
    if not token_rows:
        print("  (No verification tokens yet)")
    else:
        for tr in token_rows:
            status = "VERIFIED (Used)" if tr[2] else "PENDING (Unused)"
            print(f"  Email: {tr[1]} | Status: {status} | Created: {tr[3]}")

    conn.close()

if __name__ == "__main__":
    main()
