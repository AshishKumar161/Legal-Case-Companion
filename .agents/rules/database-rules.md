# Database Engineering Rules

Derived from `docs/02_DATABASE_DESIGN.md` (Project Source of Truth):

1. **Entity Justification**: No database entity or field may be created without traceable business justification in `docs/02_DATABASE_DESIGN.md`.
2. **Primary Keys**: Always use UUIDv7 (application-generated via `app.core.identifiers.generate_uuid7`).
3. **Timestamps**: All timestamps must be `TIMESTAMPTZ` with timezone awareness.
4. **Soft Deletion**: Core business entities (cases, clients, lawyers, documents) use soft deletion (`deleted_at`). Financial transactions, security records, and audit events must NEVER be soft-deleted.
5. **Audit Immutability**: `AuditEvent` is strictly append-only. No UPDATE, DELETE, or soft-delete operations are permitted under any circumstance.
6. **Authorization Derivation**: Authorization is derived through `CaseParticipant`. Explicit per-document grants are prohibited to prevent desynchronization.
