import sqlite3
import os
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "test.db")

def export_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [r[0] for r in cursor.fetchall()]

    output = []
    output.append("# Full Database Dump — `test.db`\n")
    output.append(f"**Database Path:** `{DB_PATH}`  \n")
    output.append(f"**Total Tables:** {len(tables)}  \n")

    non_empty_tables = []
    for t in tables:
        cursor.execute(f'SELECT COUNT(*) FROM "{t}"')
        cnt = cursor.fetchone()[0]
        if cnt > 0:
            non_empty_tables.append((t, cnt))

    output.append("### Active Tables Overview\n")
    output.append("| Table Name | Row Count |")
    output.append("| :--- | :--- |")
    for t, cnt in non_empty_tables:
        output.append(f"| [`{t}`](#table-{t.replace('_', '-')}) | **{cnt}** |")
    output.append("\n---\n")

    for t, cnt in non_empty_tables:
        output.append(f"## Table: `{t}` ({cnt} rows)\n")
        cursor.execute(f'SELECT * FROM "{t}"')
        rows = [dict(r) for r in cursor.fetchall()]
        if not rows:
            output.append("*(empty)*\n")
            continue

        columns = list(rows[0].keys())
        # Filter out password_hash to show only preview for readability
        header = "| " + " | ".join(columns) + " |"
        sep = "| " + " | ".join(["---"] * len(columns)) + " |"
        output.append(header)
        output.append(sep)

        for r in rows:
            vals = []
            for col in columns:
                val = r[col]
                if val is None:
                    vals.append("*null*")
                elif col == "password_hash" and isinstance(val, str):
                    vals.append(f"`{val[:20]}...`")
                elif col in ("token_hash", "id") and isinstance(val, str):
                    vals.append(f"`{val[:16]}...`" if len(val) > 20 else f"`{val}`")
                else:
                    s = str(val).replace("\n", " ").replace("|", "\\|")
                    if len(s) > 50:
                        s = s[:47] + "..."
                    vals.append(s)
            output.append("| " + " | ".join(vals) + " |")
        output.append("\n---\n")

    conn.close()
    return "\n".join(output)

def export_all():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    docs_dir = os.path.join(ROOT, "docs")
    os.makedirs(docs_dir, exist_ok=True)

    # 1. Export Markdown
    md_content = export_db()
    with open(os.path.join(docs_dir, "database_data.md"), "w", encoding="utf-8") as f:
        f.write(md_content)

    # 2. Export users.csv
    import csv
    cursor.execute('SELECT id, email, role, account_status, created_at, password_hash FROM users ORDER BY created_at DESC')
    users = [dict(r) for r in cursor.fetchall()]
    with open(os.path.join(docs_dir, "users.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'email', 'role', 'account_status', 'created_at', 'password_hash'])
        writer.writeheader()
        writer.writerows(users)

    # 3. Export full database.json
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [r[0] for r in cursor.fetchall()]
    all_data = {}
    for t in tables:
        cursor.execute(f'SELECT * FROM "{t}"')
        rows = [dict(r) for r in cursor.fetchall()]
        if rows:
            all_data[t] = rows

    with open(os.path.join(docs_dir, "database.json"), "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, default=str)

    # 4. Generate Interactive HTML Viewer
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Database Viewer — test.db</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 32px; margin: 0; }}
        h1 {{ font-size: 1.8rem; color: #60a5fa; margin-bottom: 8px; }}
        p {{ color: #94a3b8; font-size: 0.95rem; margin-bottom: 24px; }}
        .badge {{ background: #1e293b; border: 1px solid #334155; padding: 4px 10px; border-radius: 6px; font-size: 0.85rem; color: #38bdf8; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 36px; background: #1e293b; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
        th {{ background: #0284c7; color: white; padding: 12px; text-align: left; font-size: 0.9rem; }}
        td {{ padding: 12px; border-bottom: 1px solid #334155; font-size: 0.85rem; word-break: break-all; }}
        tr:hover {{ background: rgba(255,255,255,0.03); }}
        .hash {{ font-family: monospace; color: #f472b6; }}
        .status-active {{ color: #4ade80; font-weight: bold; }}
        .status-verified {{ color: #38bdf8; font-weight: bold; }}
        .status-pending {{ color: #facc15; font-weight: bold; }}
    </style>
</head>
<body>
    <h1>Legal Case Companion — Database Viewer</h1>
    <p>Viewing live records from <code>{DB_PATH}</code> <span class="badge">{len(tables)} Tables Available</span></p>

    <h2>1. Users (users table)</h2>
    <table>
        <tr><th>User ID</th><th>Email</th><th>Role</th><th>Account Status</th><th>Created At</th><th>Argon2id Password Hash</th></tr>
        {"".join(f"<tr><td><code>{u['id']}</code></td><td><b>{u['email']}</b></td><td>{u['role']}</td><td class='status-active'>{u['account_status']}</td><td>{u['created_at']}</td><td class='hash'>{u['password_hash'][:35]}...</td></tr>" for u in users)}
    </table>

    <h2>2. Email Verification OTP Tokens (email_verification_tokens)</h2>
    <table>
        <tr><th>Email</th><th>Status</th><th>Created At</th><th>Used / Verified At</th><th>IP</th></tr>
        {"".join(f"<tr><td><b>{t['email']}</b></td><td class='{'status-verified' if t['used_at'] else 'status-pending'}'>{'✓ VERIFIED' if t['used_at'] else '⏳ PENDING'}</td><td>{t['created_at']}</td><td>{t['used_at'] or 'Unverified'}</td><td>{t['ip_metadata'] or '-'}</td></tr>" for t in all_data.get('email_verification_tokens', []))}
    </table>

    <h2>3. Profiles</h2>
    <table>
        <tr><th>Type</th><th>Full Name</th><th>User ID</th><th>Created At</th></tr>
        {"".join(f"<tr><td>Client</td><td><b>{p['full_name']}</b></td><td><code>{p['user_id']}</code></td><td>{p['created_at']}</td></tr>" for p in all_data.get('client_profiles', []))}
        {"".join(f"<tr><td>Lawyer</td><td><b>{p['full_name']}</b></td><td><code>{p['user_id']}</code></td><td>{p['created_at']}</td></tr>" for p in all_data.get('lawyer_profiles', []))}
    </table>
</body>
</html>"""
    with open(os.path.join(docs_dir, "view_database.html"), "w", encoding="utf-8") as f:
        f.write(html_content)

    conn.close()
    print("Exported:")
    print(" - docs/database_data.md")
    print(" - docs/users.csv")
    print(" - docs/database.json")
    print(" - docs/view_database.html")

if __name__ == "__main__":
    export_all()
