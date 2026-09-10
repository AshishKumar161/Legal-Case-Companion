# Phase 11: Repository-Wide Reference & Dependency Graph

## 1. Architectural Dependency Flow

Following the Phase 10 refactor and Phase 11 cleanup, the dependency direction is strictly unidirectional:

```
                ┌──────────────────────────────┐
                │       FastAPI Routers        │ (app/api/v1/)
                └──────────────┬───────────────┘
                               │ (imports services & schemas)
                               ▼
                ┌──────────────────────────────┐
                │   Domain Application Layer   │ (app/domain/*)
                └───────┬──────────────┬───────┘
                        │              │
         (persistence)  ▼              ▼  (external integrations)
┌─────────────────────────────┐  ┌─────────────────────────────┐
│  Repositories & ORM Models  │  │ External Provider Adapters  │
│(app/repositories/, models/) │  │       (app/providers/)      │
└─────────────────────────────┘  └─────────────────────────────┘
```

---

## 2. Layer-by-Layer Module Count & Invariants

| Layer | Module Count | Allowed Inbound From | Prohibited Outbound To | Status |
| :--- | :--- | :--- | :--- | :--- |
| **API Layer** (`app/api/`) | 23 | Client / HTTP | Domain logic internals | **CLEAN** |
| **Domain Layer** (`app/domain/`) | 73 | API Routers, Background Workers | FastAPI Request/Response, SDK internals | **CLEAN** |
| **Repositories** (`app/repositories/`) | 6 | Domain Services | API Routers, External Providers | **CLEAN** |
| **Providers** (`app/providers/`) | 16 | Domain Services (via Interfaces) | API Routers, Domain Business Rules | **CLEAN** |
| **ORM Models** (`app/models/`) | 19 | Repositories, Domain Services | API Routers, Provider SDKs | **CLEAN** |
| **Schemas** (`app/schemas/`) | 18 | API Routers, Domain Services | Database Engine, ORM Models | **CLEAN** |
| **Retained Facades** (`app/services/`) | 5 | Tests (with dynamic monkeypatching) | Production code | **ISOLATED** |

---

## 3. Reference Graph Verification

### A. Production References
- Total production files importing `app.services.*`: **0**
- All API routers in `app/api/v1/` import directly from `app.domain.*`.
- All domain services import dependencies from their peer domain packages or `app/repositories/`.

### B. External Providers Decoupling
- Zero SDK leakage into domain services (`stripe`, `livekit`, `boto3` are strictly encapsulated in `app/providers/`).
- Domain services depend exclusively on abstract provider interfaces (`PaymentProvider`, `VideoProvider`, `StorageProvider`, `EmailProvider`).

### C. Dynamic References & Monkeypatch Isolation
- Only 5 backward-compatibility facades are retained in `app/services/` (`presence_service.py`, `job_service.py`, `document_processor.py`, `retrieval_service.py`, `payment_service.py`).
- These 5 are retained exclusively to support dynamic runtime test monkeypatching (e.g. `monkeypatch.setattr('app.services.presence_service.get_redis_client', ...)`).
- 66 unused facades were proven to have 0 production, 0 test, 0 script, and 0 dynamic references, and have been safely removed.

---

## 4. Circular Dependency Audit

- Circular imports detected: **0**
- Verified using topological dependency traversal across all 329 production and test modules.
