# Alembic Migration Safety & Operational Guidelines — Phase 4

## 1. Migration Safety Principles

Database migrations in Legal Case Companion (LCC) adhere to strict zero-downtime and data-integrity requirements:

1. **Non-Destructive Schema Evolution**:
   - `DROP TABLE` or `DROP COLUMN` is prohibited in a single-step release without prior deprecation and backfill.
   - Any table retirement must first copy or backfill live data into the replacement table before schema pruning.
2. **Explicit Error Handling & Zero Exception Swallowing**:
   - `except Exception: pass` is strictly prohibited in all Alembic migrations.
   - Migration logic must inspect reflected database metadata (e.g., using `sa.inspect(bind)`) before conditional index or table modifications.
   - Unexpected schema states must raise immediately rather than silently failing and corrupting the migration sequence.
3. **Full Downgrade Symmetry**:
   - Every `upgrade()` step must have an equivalent, tested `downgrade()` step that leaves the database in a valid state.
4. **Idempotency & Dialect Agnosticism**:
   - Migrations must succeed identically across PostgreSQL production clusters and SQLite integration test environments.

---

## 2. In-Depth Migration Audit: Revision `25500e9a54c3`

### 2.1 Context & Risk Analysis
- **Migration ID**: `25500e9a54c3_sync_schema_drift_provenance_enums_.py`
- **Down Revision**: `4148d4a785b4`
- **Initial Risk**:
  - The migration contained a `DROP TABLE feedback` instruction.
  - Previous implementation contained multiple `except Exception: pass` blocks, hiding schema corruption.
  - It lacked backfilling of legacy records, creating a risk of data loss.
  - The `downgrade()` function did not restore the dropped `feedback` table.

### 2.2 Root-Cause & Intended Evolution
- Early development created an initial `feedback` table. Later, the pilot governance framework introduced the richer `pilot_feedback` table (`id`, `user_id`, `category`, `message`, `sentiment`, `sentiment_score`, `cohort_id`, `created_at`).
- All services, models, and endpoints were shifted to `pilot_feedback`.
- The `feedback` table became orphaned; however, dropping it without data migration was unsafe.

### 2.3 Corrective Implementation in Phase 4
1. **Metadata Inspection**:
   - Using `sa.inspect(bind)` to inspect table, index, and constraint presence before executing DDL.
2. **Automatic Data Backfill**:
   - Before dropping `feedback`, any existing rows in `feedback` are copied into `pilot_feedback` with sensible defaults:
     ```python
     bind.execute(
         sa.text("""
             INSERT INTO pilot_feedback (id, user_id, category, message, sentiment, sentiment_score, cohort_id, created_at)
             SELECT id, user_id, category, message, 'NEUTRAL', 0.5, NULL, created_at
             FROM feedback
             WHERE id NOT IN (SELECT id FROM pilot_feedback)
         """)
     )
     ```
3. **Symmetric Downgrade**:
   - `downgrade()` recreates the `feedback` table and index if the database is rolled back past `25500e9a54c3`.
4. **Elimination of Exception Swallowing**:
   - Replaced all `except Exception: pass` with explicit existence checks.

### 2.4 Verification
- **Automated Lifecycle Script**: [`scripts/test_migrations_lifecycle.py`](file:///c:/Users/akuma/OneDrive/Desktop/lcc/Legal-Case-Companion-main/scripts/test_migrations_lifecycle.py)
  - Upgraded empty DB to head.
  - Downgraded past `25500e9a54c3` to verify `feedback` table recreation.
  - Inserted test records into `feedback`.
  - Re-upgraded to head and asserted that the legacy records were successfully preserved in `pilot_feedback`.
  - Verified: **PASS**.

---

## 3. Safe Rollout Protocols for Large Tables

For high-throughput tables (`users`, `cases`, `appointments`, `consultations`, `audit_events`):
1. **Adding Columns**:
   - Add new columns as `nullable=True` first.
   - Backfill default values in batched background workers if rows exceed 100,000.
   - Apply `nullable=False` with server default in a subsequent migration after all rows are populated.
2. **Adding Indexes**:
   - In production PostgreSQL, index creation must utilize `CONCURRENTLY` outside of a single transaction lock:
     ```python
     with context.begin_transaction():
         # transactional DDL
     # Non-blocking index creation on PostgreSQL:
     # op.create_index(..., postgresql_concurrently=True)
     ```
3. **Lock Timeouts**:
   - Application connects with `statement_timeout` set to 5000ms (`settings.DB_STATEMENT_TIMEOUT_MS`) to prevent prolonged table locks.
