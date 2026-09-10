# Phase 10: Dead Code & Deprecation Candidates

**Phase 10 Policy:** DO NOT delete compatibility shims or legacy facades until all internal and external callers have conclusively migrated. This document records all identified candidates, their current references, safe deletion conditions, and target phase for retirement.

---

## Candidate Inventory

### 1. `app/db/session.py`
- **Current Role:** Compatibility shim re-exporting `SessionLocal`, `engine`, and `get_db` from `app.db.database`.
- **Why It Looks Dead:** The primary application codebase and routers standardly import from `app.db.database` directly (e.g. `from app.db.database import get_db`).
- **References:**
  - `scripts/cleanup_test_lawyers.py`
  - `scripts/run_scale_validation.py`
  - `scripts/seed_pilot_demo.py`
  - `scripts/load_test_phase_10.py`
  - `scripts/measure_performance_baseline.py`
  - Operational runbooks in `docs/23_INCIDENT_RESPONSE.md`
- **Dynamic References:** None.
- **Safe to Delete Now?** **NO.** Operational maintenance scripts and disaster recovery runbooks still reference `app.db.session`.
- **Migration Plan:** Update script imports in Phase 11 to import from `app.db.database`.
- **Target Phase for Removal:** Phase 12.

---

### 2. `app/services/ai_provider.py`
- **Current Role:** Compatibility facade re-exporting `AIProvider`, `StubAIProvider`, `ProductionOpenAIProvider`, and prompt sanitizers from canonical `app.providers.ai`.
- **Why It Looks Dead:** Phase 6 established the canonical AI provider abstraction under `app/providers/ai/`.
- **References:**
  - `tests/security/test_ai_privacy.py`
  - `tests/security/test_phase_6_ai_security.py`
  - `tests/integration/test_instant_consultation_flow.py`
- **Dynamic References:** None.
- **Safe to Delete Now?** **NO.** Security tests and benchmark harnesses actively import stub and provider interfaces from this facade.
- **Migration Plan:** Direct test imports to `app.domain.ai.ai_provider` or `app.providers.ai`.
- **Target Phase for Removal:** Phase 12.

---

### 3. `app/services/legal_source_providers/`
- **Current Role:** Provider adapter implementations for e-Courts and fixture ingestion (`base.py`, `curated_fixtures.py`, `ecourts_provider.py`).
- **Why It Looks Dead:** In Phase 10, legal intelligence and authority ingestion were migrated into `app/domain/ai/legal_source_providers/`.
- **References:**
  - `app/services/legal_data_pipeline.py` (facade)
  - `tests/integration/test_legal_data_pipeline.py`
- **Dynamic References:** None.
- **Safe to Delete Now?** **NO.** Retained as a backward-compatibility location for pipeline test harnesses.
- **Migration Plan:** Deprecate in Phase 11 after pipeline test harnesses are verified.
- **Target Phase for Removal:** Phase 12.

---

### 4. `app/services/*.py` (75 Service Compatibility Facades)
- **Current Role:** Transparent re-export facades mapping old service paths (`app.services.<service_name>`) to canonical domain packages (`app.domain.<domain>.<service_name>`).
- **Why They Look Dead:** All canonical business logic now resides in `app/domain/`.
- **References:**
  - Existing legacy test files and ad-hoc scripts throughout `tests/` and `scripts/`.
- **Dynamic References:** None.
- **Safe to Delete Now?** **NO.** Removing these facades would break legacy imports across historical test suites without business benefit.
- **Migration Plan:** Incrementally migrate test imports in Phase 11; verify zero external dependencies before deletion.
- **Target Phase for Removal:** Phase 12.

---

## Summary Matrix

| Candidate | Category | Current Status | Safe to Delete? | Target Phase |
|---|---|---|---|---|
| `app/db/session.py` | Legacy Database Shim | Active in scripts | NO | Phase 12 |
| `app/services/ai_provider.py` | Provider Facade | Active in tests | NO | Phase 12 |
| `app/services/legal_source_providers/` | Ingestion Adapters | Active in tests | NO | Phase 12 |
| `app/services/*.py` (75 facades) | Compatibility Facades | Active across legacy tests | NO | Phase 12 |
