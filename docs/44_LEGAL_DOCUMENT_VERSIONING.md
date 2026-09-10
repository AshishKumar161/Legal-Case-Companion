# Phase XX: Legal Document Versioning & Consent Auditability

## Overview
LCC enforces versioning for all user-facing legal and policy documents per Digital Personal Data Protection (DPDP) Act, 2023 requirements and Indian Contract Act principles.

## Document Versioning Model
Every policy document exists as a distinct immutable record in `legal_document_versions`:
- `document_type`: `TERMS_OF_SERVICE`, `ADVOCATE_TERMS`, `PRIVACY_NOTICE`, `AI_DISCLOSURE`, `EVIDENCE_STORAGE_NOTICE`, `CONSULTATION_DISCLOSURE`, `COOKIE_NOTICE`.
- `version`: Semantic version string (`2.0.0`).
- `locale`: Target language (`en-IN`, `hi-IN`).
- `effective_at`: Explicit statutory timestamp.
- `publication_status`: `DRAFT`, `PUBLISHED`, `SUPERSEDED`, `ARCHIVED`.
- `approved_by` / `approved_at`: Formal audit trail of human legal counsel sign-off.

## Non-Repudiable Consent Audit Trail
When a user accepts a policy version:
- Recorded in `user_document_consents` with non-repudiable metadata.
- Hashes of client IP and User-Agent are stored (`ip_hash`, `user_agent_hash`) to preserve evidentiary integrity without retaining raw PII.
- Historical consents are **never overwritten or deleted**, ensuring an unbroken compliance ledger.
