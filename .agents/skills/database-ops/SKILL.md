---
name: database-ops
description: >-
  Procedures for inspecting database models, validating table schemas, and verifying Alembic
  migrations using the lcc-database MCP server.
---

# Database Operations & Schema Intelligence Skill

Use this skill whenever creating new database tables, modifying existing columns, generating migrations, or verifying model alignment with `docs/02_DATABASE_DESIGN.md`.

## Available Database Tools

- `db_list_tables()`: Discover all tables declared in `app/models/`.
- `db_get_table_schema(table_name)`: Inspect column definitions, datatypes, and constraints.
- `db_check_migrations()`: Review the Alembic migration history and head revision.
- `db_execute_readonly_query(sql_query, limit)`: Execute safe read-only SQL queries to verify data.

## Standard Workflow for Schema Evolution

1. **Verify Head Revision**:
   Call `db_check_migrations()` to identify the latest revision ID.
2. **Consult Database Design**:
   Reference `docs/02_DATABASE_DESIGN.md` for entity ownership, UUIDv7 requirement, and soft-delete rules.
3. **Model Implementation**:
   Add or update models in `app/models/`. Ensure all foreign keys have corresponding indexes and cascade rules.
4. **Migration Generation**:
   Run `alembic revision --autogenerate -m "descriptive message"`.
5. **Contract Verification**:
   Inspect the new table definition via `db_get_table_schema()` and verify zero schema drift.
