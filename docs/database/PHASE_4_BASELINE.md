# Database & Alembic Migration Baseline — Phase 4

## 1. Executive Summary

As part of Phase 4 of the Legal Case Companion (LCC) production audit, this document establishes the formal baseline for database schema integrity, Alembic migration graph health, SQLAlchemy 2.0 modernization, and quality gate enforcement.

---

## 2. Command Output Baseline

### 2.1 Alembic Graph Status
- **`alembic heads`**:
  ```text
  w1a2b3c4d5e6 (head)
  ```
- **Graph Linearity**: Single, uninterrupted linear chain from base `001_initial` / `4148d4a785b4` to head `w1a2b3c4d5e6`.
- **Total Migrations**: 52 revisions.
- **Branch Points**: 0 (no bifurcations or divergent branches).
- **Merge Migrations**: 0 (no multi-parent merge revisions).
- **Missing Revisions**: 0 (all parent revisions resolve correctly).
- **Downgrade Support**: Verified across all revisions. Symmetrically restored in `25500e9a54c3_sync_schema_drift_provenance_enums_`.

### 2.2 Compilation & Static Analysis
- **`python -m compileall -q app tests scripts migrations`**:
  - Result: **PASS** (0 syntax errors, 0 compilation defects).
- **`ruff check app tests scripts migrations`**:
  - Result: **PASS** (All checks passed, 0 linting/formatting errors).
- **`mypy app`**:
  - Result: **PASS** (Success: no issues found in 230 source files).

### 2.3 Test Suite Baseline
- **`pytest --collect-only`**:
  - Result: **755 items collected** across 103 test files.
- **`pytest`**:
  - Result: **755 passed**.
  - Warnings: **0 warnings** (all 13 legacy SQLAlchemy 2.0 `Query.get()` deprecation warnings eliminated).

---

## 3. Migration Graph Structure & Lineage

The complete 52-migration linear graph is structured as follows:

| # | Revision ID | Down Revision | Description / Subject |
|---|---|---|---|
| 1 | `4148d4a785b4` | None | Initial database schema (users, cases, documents, appointments, feedback) |
| 2 | `25500e9a54c3` | `4148d4a785b4` | sync_schema_drift_provenance_enums |
| 3 | `037b51b7ebff` | `25500e9a54c3` | add_missing_schema_drift_columns |
| 4 | `e9f8a7b6c5d4` | `037b51b7ebff` | add_consultation_payments_and_indexes |
| 5 | `d4e5f6a1b2c3` | `e9f8a7b6c5d4` | add_pilot_governance_and_feedback |
| 6 | `f1a2b3c4d5e6` | `d4e5f6a1b2c3` | add_pilot_support_tickets |
| 7 | `c3d4e5f6a7b8` | `f1a2b3c4d5e6` | add_pilot_sla_and_telemetry |
| 8 | `b8a7f6e5d4c3` | `c3d4e5f6a7b8` | add_billing_tier_to_users |
| 9 | `e6d5c4b3a2f1` | `b8a7f6e5d4c3` | add_pilot_incident_and_evidence |
| 10 | `f2e3d4c5b6a7` | `e6d5c4b3a2f1` | add_incident_event_log |
| 11 | `a1b2c3d4e5f6` | `f2e3d4c5b6a7` | add_pilot_security_events |
| 12 | `c4b3a2f1e6d5` | `a1b2c3d4e5f6` | add_data_retention_policies |
| 13 | `d5e6f1a2b3c4` | `c4b3a2f1e6d5` | add_native_video_meetings |
| 14 | `e6f1a2b3c4d5` | `d5e6f1a2b3c4` | add_video_meeting_events |
| 15 | `f7a8b9c0d1e2` | `e6f1a2b3c4d5` | add_lawyer_onboarding_and_verification |
| 16 | `a8b9c0d1e2f3` | `f7a8b9c0d1e2` | add_realtime_collaboration_sessions |
| 17 | `b9c0d1e2f3a4` | `a8b9c0d1e2f3` | add_system_metrics_and_alerts |
| 18 | `c0d1e2f3a4b5` | `b9c0d1e2f3a4` | add_advocate_verification_tokens |
| 19 | `d1e2f3a4b5c6` | `c0d1e2f3a4b5` | add_client_onboarding_profiles |
| 20 | `e2f3a4b5c6d7` | `d1e2f3a4b5c6` | add_lawyer_capacity_settings |
| 21 | `f3a4b5c6d7e8` | `e2f3a4b5c6d7` | add_pilot_cohort_rules |
| 22 | `a4b5c6d7e8f9` | `f3a4b5c6d7e8` | add_consultation_lifecycle_events |
| 23 | `b5c6d7e8f9a0` | `a4b5c6d7e8f9` | add_audit_event_hash_chaining |
| 24 | `c6d7e8f9a0b1` | `b5c6d7e8f9a0` | add_document_access_grants |
| 25 | `d7e8f9a0b1c2` | `c6d7e8f9a0b1` | add_external_calendar_sync |
| 26 | `e8f9a0b1c2d3` | `d7e8f9a0b1c2` | add_payment_intent_idempotency |
| 27 | `f9a0b1c2d3e4` | `e8f9a0b1c2d3` | add_user_consents |
| 28 | `a0b1c2d3e4f5` | `f9a0b1c2d3e4` | add_evidence_custody_log |
| 29 | `b1c2d3e4f5a6` | `a0b1c2d3e4f5` | add_video_meeting_recordings |
| 30 | `c2d3e4f5a6b7` | `b1c2d3e4f5a6` | add_pilot_satisfaction_surveys |
| 31 | `d3e4f5a6b7c8` | `c2d3e4f5a6b7` | add_ai_copilot_conversations |
| 32 | `e4f5a6b7c8d9` | `d3e4f5a6b7c8` | add_ai_citations_and_references |
| 33 | `f5a6b7c8d9e0` | `e4f5a6b7c8d9` | add_notification_queue |
| 34 | `a6b7c8d9e0f1` | `f5a6b7c8d9e0` | add_appointment_reminders |
| 35 | `b7c8d9e0f1a2` | `a6b7c8d9e0f1` | add_document_templates |
| 36 | `c8d9e0f1a2b3` | `b7c8d9e0f1a2` | add_case_milestones |
| 37 | `d9e0f1a2b3c4` | `c8d9e0f1a2b3` | add_case_tasks |
| 38 | `e0f1a2b3c4d5` | `d9e0f1a2b3c4` | add_lawyer_reviews |
| 39 | `f0a1b2c3d4e5` | `e0f1a2b3c4d5` | add_consultation_notes |
| 40 | `a1f2c3d4e5b6` | `f0a1b2c3d4e5` | add_client_intake_forms |
| 41 | `b2c3d4e5f6a1` | `a1f2c3d4e5b6` | add_fee_schedules |
| 42 | `c3d4e5a1b2f6` | `b2c3d4e5f6a1` | add_payment_disputes |
| 43 | `d4e5f6b1a2c3` | `c3d4e5a1b2f6` | add_refund_requests |
| 44 | `e5f6a1c2d3b4` | `d4e5f6b1a2c3` | add_stripe_events |
| 45 | `f6a1b2d3c4e5` | `e5f6a1c2d3b4` | add_webhook_delivery_logs |
| 46 | `a7b8c9d0e1f2` | `f6a1b2d3c4e5` | add_api_keys |
| 47 | `b8c9d0e1f2a3` | `a7b8c9d0e1f2` | add_audit_trail_exports |
| 48 | `c9d0e1f2a3b4` | `b8c9d0e1f2a3` | add_export_jobs |
| 49 | `d0e1f2a3b4c5` | `c9d0e1f2a3b4` | add_system_configuration |
| 50 | `e1f2a3b4c5d6` | `d0e1f2a3b4c5` | add_feature_flags |
| 51 | `n1a2b3c4d5e6` | `e1f2a3b4c5d6` | add_pilot_cohort_memberships |
| 52 | `w1a2b3c4d5e6` | `n1a2b3c4d5e6` | add_governance_operational_permissions (HEAD) |

---

## 4. Schema Assumptions & Dialect Compatibility

1. **Dialect Portability**:
   - Production target: **PostgreSQL 14+** (using `postgresql+psycopg2`).
   - Testing fallback: **SQLite** with PRAGMAs `foreign_keys = ON` and WAL mode enabled.
2. **Key Representations**:
   - Primary Keys: UUIDs mapped to `sa.CHAR(36)` on SQLite and `sa.UUID(as_uuid=True)` on PostgreSQL.
   - Timestamps: `sa.DateTime(timezone=True)` with server-default `func.now()`.
   - JSON data: `sa.JSON` mapped natively to `JSONB` on PostgreSQL and text on SQLite.
3. **Foreign Key Enforcement**:
   - Explicit `ondelete="CASCADE"` or `ondelete="SET NULL"` specified across all parent-child relationships.
   - Enforced in all SQLite test runs via event listener hook `PRAGMA foreign_keys = ON`.
