# Phase 8: Frontend Architecture & Integration Hardening Report

## 1. Executive Summary

As part of Phase 8 for the **Legal Case Companion (LCC)** platform, a comprehensive audit, consolidation, and architectural hardening was conducted across the Next.js frontend application and its integration with the FastAPI backend. 

Key results achieved:
- **Baseline Preserved**: Zero regressions across existing backend suites (833 baseline tests + 8 new contract tests = 841 passed, 129 security tests passed, Mypy 0 errors, Ruff 0 errors).
- **Frontend Code Quality**: TypeScript typecheck 0 errors (`tsc --noEmit`), ESLint 0 errors and **0 warnings** (down from 31 baseline warnings), Next.js production build **PASS** (36/36 static/dynamic routes compiled).
- **Canonical API Layer**: Direct, fragmented `fetch()` calls eliminated; standardized domain-driven API modules established in `frontend/src/lib/api/` (`auth`, `cases`, `documents`, `consultations`, `ai`, `payments`, `verification`).
- **Component Consolidation**: Consolidated UI primitives (`EmptyState`, `Skeleton`/`LoadingSkeleton`), integrated rich functional matter components (`MatterBriefCard`, `MatterParticipantsPanel`) directly into the active matter workspace.
- **Resource & Memory Safety**: Closed critical WebSocket timer leaks in `consultations/[id]/room`, added strict interval unmounting cleanup, and replaced legacy `window.location.href` assignments with Next.js router transitions.
- **Accessibility & UX**: Added ARIA live-regions (`role="status"`, `aria-live="polite"`), system-wide reduced motion support (`@media (prefers-reduced-motion)`), accessible empty/loading states, and standard 404 boundary.

---

## 2. Next.js App Router Architecture

The frontend is structured under `frontend/src/app/` leveraging the Next.js 14+ App Router:

```
frontend/src/app/
├── (routes)/
│   ├── page.tsx                     # Landing / Hero / Role switcher
│   ├── login/page.tsx               # Isolated tab session authentication
│   ├── register/page.tsx            # Client & Lawyer onboarding flow
│   ├── verify-email/page.tsx        # 6-digit OTP verification & link handler
│   ├── dashboard/page.tsx           # Client case overview & quick actions
│   ├── calendar/page.tsx            # Unified court hearings & consultation schedules
│   ├── documents/page.tsx           # Global document management & OCR status
│   ├── notifications/page.tsx       # System, matter, and consultation alerts
│   ├── settings/page.tsx            # Profile, security, and locale settings
│   ├── admin/
│   │   ├── dashboard/page.tsx       # System telemetry, audit logs, queue stats
│   │   └── verification/page.tsx    # Bar council advocate verification queue
│   ├── cases/
│   │   ├── new/page.tsx             # Multipart matter intake wizard
│   │   └── [caseId]/
│   │       ├── page.tsx             # Matter workspace (Tabs: Overview, Timeline, People, Docs, Intelligence)
│   │       ├── bundle/page.tsx      # Evidentiary court bundle generator
│   │       ├── hearing/page.tsx     # Court hearing timeline & tracking
│   │       └── tracking/page.tsx    # CNR court tracker & case status
│   ├── consultations/
│   │   ├── page.tsx                 # Consultation booking & listing
│   │   └── [id]/
│   │       ├── page.tsx             # Booking detail & join-window countdown
│   │       └── room/page.tsx        # WebRTC video room, screen share, document share, chat
│   └── lawyers/
│       ├── page.tsx                 # Advocate search directory & filters
│       └── [lawyerId]/page.tsx      # Advocate profile, credentials, booking wizard
├── layout.tsx                       # Root layout with AuthProvider & QueryClientProvider
├── error.tsx                        # Global runtime error boundary
├── loading.tsx                      # Top-level loading fallback
└── not-found.tsx                    # Branded accessible 404 handler
```

### Route Inventory & Access Matrix

| Route Category | Public / Protected | Authorized Roles | Primary API Endpoints | State Owner |
|---|---|---|---|---|
| `/` | Public | All | None | Local UI |
| `/login`, `/register`, `/verify-email` | Public | Unauthenticated | `/api/v1/auth/*` | AuthContext + SessionStorage |
| `/dashboard` | Protected | `CLIENT`, `LAWYER`, `ADMIN` | `/api/v1/cases`, `/api/v1/consultations` | Server State / React Query |
| `/cases/[caseId]` | Protected | Case Participants | `/api/v1/cases/{id}/workspace`, `/reports` | Matter Workspace State |
| `/cases/[caseId]/bundle` | Protected | Case Participants | `/api/v1/cases/{id}/bundles` | Local Builder State |
| `/consultations/[id]/room` | Protected | Client + Assigned Lawyer + Admin | `/api/v1/consultations/{id}/video/*` | WebRTC + WS Signaling Manager |
| `/admin/*` | Protected | `ADMIN` strictly | `/api/v1/admin/*`, `/api/v1/verification/*` | Admin Queue State |

---

## 3. Canonical API Client Architecture

### 3.1 Design Principles
1. **Zero Direct `fetch()` or Ad-hoc URL Building**: All network calls route through `frontend/src/lib/api/client.ts` or its domain-specific modules.
2. **Tab-Isolated Token Injection**: Access tokens are stored per-browser-tab via `sessionStorage` with custom UUID `tab_session_id`, injected through HTTP `Authorization: Bearer <token>` headers.
3. **Blob & Binary Support**: Extended the core client with `apiClient.blob(...)` to support file downloads and report exports without losing authorization headers.
4. **Structured Error Handling**: All HTTP 4xx/5xx responses are normalized into `ApiError` instances exposing `status`, `message`, `details`, and `code`.
5. **Contract Compatibility**: Frontend interfaces match backend Pydantic schemas without arbitrary field renaming.

### 3.2 Canonical Domain Modules (`frontend/src/lib/api/`)
- `client.ts`: Canonical API client base, request interceptor, session management, and `blob` handling.
- `auth.ts`: Authentication, registration, token refresh, OTP verification, and current user retrieval.
- `cases.ts`: Case workspace hydration, CRUD operations, timeline events, participant management, and markdown/json report export.
- `documents.ts`: Presigned upload URL generation, upload completion confirmation, and consultation document sharing.
- `consultations.ts`: Meeting scheduling, reschedule/cancel, room access-status evaluation, WebRTC join credentials, and recordings.
- `ai.ts`: Kanoon hybrid legal authority search, AI assistant prompt queries, and streaming response handlers.
- `payments.ts`: Payment intent creation with client-supplied idempotency keys and mock payment simulation.
- `verification.ts`: Advocate bar council credential review, document inspection, and approval/rejection workflows.

---

## 4. State Management Architecture

| Layer | Technology / Pattern | Scope | Persistence | Invalidation Mechanism |
|---|---|---|---|---|
| **Authentication & Identity** | `AuthProvider` (React Context) | Tab Session | `sessionStorage` (`lcc_access_token_{tabId}`) | Explicit logout, 401 response event (`lcc:session-expired`) |
| **Server State & Queries** | TanStack React Query (`@tanstack/react-query`) | Global App | In-Memory Cache | Mutation `queryClient.invalidateQueries(...)`, Window focus |
| **Realtime WebRTC / Signaling** | WebSocket + `useRef` handles | Consultation Room | Component Lifetime | Component unmount, WS `close`, room termination event |
| **URL & Filter State** | Next.js `useRouter`, `useSearchParams` | Route Level | Browser History | Param updates via `router.push()` / `router.replace()` |
| **Local Interactive State** | `useState`, `useReducer` | Component Level | In-Memory | Component unmount |

---

## 5. Security & Authorization-Aware UI

### 5.1 Role-Based UI Guardrails
- **Defense in Depth**: UI components conditionally render based on `user.role` (`CLIENT`, `LAWYER`, `ADMIN`), but the backend remains the strict authorization boundary.
- **Navigation Guarding**: Protected route layouts inspect `user.role`. An unauthenticated request triggers redirect to `/login?redirect=...`. Unauthorized access to `/admin` redirects to `/dashboard`.
- **Cross-Tab Session Isolation**: Tab-scoped session storage prevents accidental role bleeding when a user opens multiple tabs with different test accounts.

### 5.2 XSS & Content Sanitization
- Evaluated all instances of `dangerouslySetInnerHTML`. Confirmed that no raw, untrusted user inputs are rendered as HTML. AI markdown output is sanitized before display.
- External URLs for bar council verification documents are validated for valid schemes (`https:`) before rendering links.

---

## 6. Realtime Signaling & Video Lifecycle

In `frontend/src/app/consultations/[id]/room/page.tsx`:
1. **Access Status Pre-flight**: Verifies server eligibility via `/api/v1/consultations/{id}/video/access-status` before requesting join credentials.
2. **Cryptographic Token Join**: Retrieves signed join information via `/api/v1/consultations/{id}/video/join`.
3. **Signaling Connection**: Establishes WebRTC signaling via WebSocket (`/video/ws?token=...`).
4. **Leak Prevention**: Fixed WebSocket heartbeat interval timer (`pingIntervalRef`) which previously risked memory leaks on component unmount or connection drops.
5. **Device & Track Cleanup**: Media tracks (`stream.getTracks().forEach(t => t.stop())`) are rigorously terminated in the `useEffect` cleanup return.

---

## 7. Verification & Stability Metrics

- **Backend Pytest**: 841/841 passed
- **Security Tests**: 129/129 passed
- **TypeScript (`tsc`)**: 0 errors
- **ESLint**: 0 errors, 0 warnings
- **Production Build**: Successful (36 routes)
