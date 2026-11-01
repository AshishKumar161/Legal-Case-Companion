# LCC PHASE 4 — FRONTEND, API INTEGRATION, CLIENT-SIDE SECURITY & DATA-FLOW AUDIT FINDINGS

---

### Finding ID: FE-FIND-01
**Severity:** HIGH  
**Classification:** [VERIFIED]  
**Title:** Production Document Upload Directly Invokes Mock Scanner Endpoint to Force Safe Status  

**Affected Frontend Area:** Case Workspace / Document Upload Pipeline  

**Exact File(s):**  
- `frontend/src/app/cases/[caseId]/page.tsx`  

**Exact Function/Component/Hook:**  
- `handleFileUpload` (lines 345–385)  

**Backend Endpoint(s):**  
- `POST /api/v1/documents/{document_id}/scan?is_safe=true`  
- `POST /api/v1/documents/{document_id}/complete`  

**Evidence:**  
In `frontend/src/app/cases/[caseId]/page.tsx`, during the standard document upload sequence, lines 367–368 execute:
```typescript
// 3. Mark complete & trigger virus scan
await apiClient.post(`/api/v1/documents/${doc.id}/complete`, {}).catch(() => {});
await apiClient.post(`/api/v1/documents/${doc.id}/scan?is_safe=true`, {}).catch(() => {});
```
The endpoint `POST /api/v1/documents/{document_id}/scan` is the backend `simulate_malware_scan` endpoint (`app/api/v1/documents.py:526`), originally authored as a development testing mock. By explicitly invoking this development endpoint with the query parameter `?is_safe=true`, the frontend forces the document's `security_status` directly from `PENDING` to `SAFE`, bypassing asynchronous ClamAV malware scanning.

**Failure Scenario:**  
A user uploads an infected PDF or executable file to a legal case. The browser client automatically issues a POST request to `/api/v1/documents/${doc.id}/scan?is_safe=true`. The backend marks the file `SAFE` without executing actual anti-malware analysis. Other case participants (clients, advocates, judges) download the file via `GET /documents/{id}/download` assuming it passed rigorous platform security validation. Alternatively, if an operator disables the mock scanner endpoint in production, every user upload fails or hangs indefinitely in `PENDING` status.

**User/Data Impact:**  
Exposes platform users to potential malware propagation through privileged legal case files.

**Security Impact:**  
Bypasses the malware scanning security control; client dictates security classification to the server.

**Existing Mitigation:**  
The presigned S3 upload itself enforces file size and MIME constraints, but malware inspection is bypassed.

**Missing Control:**  
Remove the client-side call to `simulate_malware_scan`. Document scanning must be triggered solely on the server via background worker tasks or S3 upload event notifications.

**Test Coverage:**  
`tests/integration/test_document_pipeline_e2e.py` validates backend scanning, but lacks an E2E test verifying that the frontend does not invoke development bypass endpoints.

**Related Phase 1 Finding:** `AUTH-DOC-01` (Development Endpoint Exposure)  
**Related Phase 2 Finding:** `DB-FIND-10` (External Side Effects)  
**Related Phase 3 Finding:** `BL-FIND-06` (Exception Swallowing via `.catch(() => {})`)  

---

### Finding ID: FE-FIND-02
**Severity:** HIGH  
**Classification:** [VERIFIED]  
**Title:** Client-Side Consultation Room Exposes URL-Driven Time-Window Bypass Parameter  

**Affected Frontend Area:** Virtual Consultation Room / Video Meeting  

**Exact File(s):**  
- `frontend/src/app/consultations/[id]/room/page.tsx`  
- `frontend/src/lib/api/consultations.ts`  

**Exact Function/Component/Hook:**  
- `VideoConsultationRoomPage` (lines 81–87)  
- `consultationsApi.getAccessStatus` (lines 64–68)  
- `consultationsApi.joinVideoMeeting` (lines 70–74)  

**Backend Endpoint(s):**  
- `GET /api/v1/consultations/{id}/video/access-status?bypass_time=true`  
- `POST /api/v1/consultations/{id}/video/start?bypass_time=true`  

**Evidence:**  
In `frontend/src/app/consultations/[id]/room/page.tsx`, lines 81–87 inspect the browser window's URL query string:
```typescript
const [bypassTimeWindow, setBypassTimeWindow] = useState<boolean>(() => {
  if (typeof window !== "undefined") {
    const p = new URLSearchParams(window.location.search);
    return p.get("bypass_time") === "true" || p.get("test") === "true";
  }
  return false;
});
```
This state variable is directly passed to the consultation room API:
```typescript
const statusRes = await consultationsApi.getAccessStatus(consultationId, bypassTimeWindow);
...
const startRes = await apiClient.post(
  `/api/v1/consultations/${consultationId}/video/start${bypassTimeWindow ? "?bypass_time=true" : ""}`,
  {}
);
```
If the query parameter is present in the URL, the client forwards `?bypass_time=true` to the backend.

**Failure Scenario:**  
A consultation is scheduled for three days in the future. A participant navigates to `/consultations/{id}/room?bypass_time=true`. The frontend activates `bypassTimeWindow`, requesting the backend to bypass scheduled start time window restrictions. If the backend is running in non-strict mode or fails to reject unauthorized bypass flags, the meeting room is initialized prematurely, generating SFU tokens and incurring unnecessary live video infrastructure costs.

**User/Data Impact:**  
Premature room access and confusing consultation countdown timers for clients and advocates.

**Security Impact:**  
Exposes a backend testing mechanism to end-user manipulation via simple URL manipulation.

**Existing Mitigation:**  
Backend `VideoAccessService` validates time windows, but accepts the parameter if configured for testing.

**Missing Control:**  
Strip `bypass_time` and `test` query parameters from production client code; bypass flags must only be accessible via authenticated administrator debug headers or restricted API scopes.

**Test Coverage:**  
`tests/integration/test_consultation_room_time_access.py` tests time enforcement, but does not assert that client code strips test flags.

**Related Phase 1 Finding:** `AUTH-CONSULT-01` (Consultation Access Controls)  
**Related Phase 2 Finding:** None  
**Related Phase 3 Finding:** `BL-FIND-04` (Consultation Lifecycle Transitions)  

---

### Finding ID: FE-FIND-03
**Severity:** MEDIUM  
**Classification:** [VERIFIED]  
**Title:** OAuth Callback Uses `router.push()` Leaving Code and State in Browser History Causing Replay Failures  

**Affected Frontend Area:** Authentication / Google OAuth Flow  

**Exact File(s):**  
- `frontend/src/app/auth/callback/page.tsx`  

**Exact Function/Component/Hook:**  
- `AuthCallbackContent.processCallback` (lines 118–131)  

**Backend Endpoint(s):**  
- `POST /api/v1/auth/google/callback`  

**Evidence:**  
In `frontend/src/app/auth/callback/page.tsx`, following successful identity verification and session establishment, lines 118–131 execute:
```typescript
if (userRole === "ADMIN") {
  router.push(safeReturnUrl || "/admin/dashboard");
} else if (!isKycCompleted) {
  router.push(targetUrl);
} else if (safeReturnUrl && safeReturnUrl !== "/dashboard") {
  router.push(safeReturnUrl);
} else if (userRole === "LAWYER") {
  router.push("/lawyer/dashboard");
} else {
  router.push("/dashboard");
}
```
Using `router.push()` pushes the callback URL (`/auth/callback?code=...&state=...`) onto the browser's session history stack rather than replacing the current entry.

**Failure Scenario:**  
A user successfully logs in via Google OAuth and lands on `/dashboard`. The user clicks the browser Back button. The browser navigates back to `/auth/callback?code=...&state=...`, triggering `processCallback()` once more. The frontend submits the already-consumed authorization code and state token to the backend. The backend rejects the request with `AuthenticationError: OAuth state has already been used. Replay detected.` The user is presented with a red error screen stating "Authentication failed during Google identity verification", causing confusion.

**User/Data Impact:**  
Degraded user experience, false-alarm authentication error screens, and unnecessary token exchange requests to backend and Google endpoints.

**Security Impact:**  
Authorization codes and state tokens remain present in the browser history stack and browser URL bar until pushed out by further navigation.

**Existing Mitigation:**  
`requestSentRef` prevents double-invocation during initial mount in React StrictMode, but does not handle backward browser navigation.

**Missing Control:**  
Replace all instances of `router.push(...)` in `auth/callback/page.tsx` with `router.replace(...)` or call `window.history.replaceState({}, document.title, window.location.pathname)` immediately upon extracting callback parameters.

**Test Coverage:**  
`frontend/scripts/test_browser_flow.mjs` tests forward navigation, but does not test Back-button navigation after OAuth callbacks.

**Related Phase 1 Finding:** `SEC-FIND-03` (OAuth State Single-Use Replay)  
**Related Phase 2 Finding:** `DB-FIND-09` (OAuth State Process-Memory Inconsistency)  
**Related Phase 3 Finding:** None  

---

### Finding ID: FE-FIND-04
**Severity:** LOW  
**Classification:** [VERIFIED]  
**Title:** Absence of Edge/Server Middleware for Pre-Hydration Navigation Protection Resulting in Post-Hydration Route Guard Dependency  

**Affected Frontend Area:** Routing / Application Shell / Pre-Hydration Navigation Protection  

**Exact File(s):**  
- `frontend/src/app/layout.tsx`  
- `frontend/src/components/AppShell/AppShell.tsx`  
- `frontend/src/app/admin/users/page.tsx`  

**Exact Function/Component/Hook:**  
- `RootLayout` (`frontend/src/app/layout.tsx`)  
- `AppShell` (`frontend/src/components/AppShell/AppShell.tsx:18–30`)  
- Page-level route protection in `frontend/src/app/**/page.tsx`  

**Backend Endpoint(s):**  
- All Protected Backend Endpoints (`/api/v1/admin/*`, `/api/v1/cases/*`, etc.)  

**Evidence:**  
Static analysis of `frontend/src/` confirms there is no Next.js `middleware.ts` (or `proxy.ts`). Route protection and authentication redirection are handled exclusively client-side in React components after initial page delivery and browser hydration:
1. In `AppShell.tsx` (lines 19–30):
```typescript
const isPublicRoute =
  pathname === "/" ||
  pathname === "/login" ||
  pathname === "/register" ||
  pathname?.startsWith("/auth/callback");

const isRoomRoute =
  Boolean(pathname?.includes("/consultations/") && pathname?.includes("/room"));

if (isPublicRoute || isRoomRoute || !user) {
  return <>{children}</>;
}
```
If `user` is null (unauthenticated), `AppShell` does not issue a redirect; it returns `<>{children}</>`. Individual pages are expected to implement their own `useEffect` guards.
2. In guarded pages (e.g. `admin/dashboard/page.tsx:202–210`):
```typescript
useEffect(() => {
  if (!loading && !user) {
    router.push("/login");
  } else if (user && user.role !== "ADMIN") {
    router.push("/dashboard");
  } else if (user) {
    void fetchAdminData();
  }
}, [user, loading, router, fetchAdminData]);
```
3. In unguarded pages (e.g. `frontend/src/app/admin/users/page.tsx`), no `useAuth()` check or redirect hook exists at all, rendering mock team member data directly to unauthenticated visitors.

**Required Architectural Distinctions:**  
- **Public vs Confidential Bundles:** Client-side JavaScript bundles served under `/_next/static/` are public web assets by design; adding Next.js server middleware does *not* make client-side bundles confidential or prevent users from inspecting client code.
- **Authoritative Data Boundary:** The backend FastAPI authorization dependencies (`get_current_user`, `RequireRole([UserRole.ADMIN])`) serve as the authoritative security boundary. No authenticated backend database records are accessible without valid JWT credentials, even if an unauthorized user renders a client-side admin view.
- **Pre-Hydration vs Post-Hydration Protection:** Without server-side middleware, direct HTTP navigation (`GET /admin/dashboard`) returns HTTP 200 with the full HTML page shell instead of an HTTP 307/302 redirect. The browser must boot React, run `AuthProvider.checkSession()`, evaluate `useEffect`, and only then execute `router.push('/login')`. This creates UI layout flashing, unneeded asset downloads, and allows unauthenticated users to interact with client-only mock interfaces on unguarded routes (such as `/admin/users`).
- **Server Secrets Protection:** Next.js environment variables prefixed with `NEXT_PUBLIC_` are intentionally exposed to the browser. No server-only secrets (such as database credentials or JWT signing secrets) are bundled into client code.

**Failure Scenario:**  
An unauthenticated visitor directly navigates to `https://app.lcc.in/admin/users`. Because no edge middleware intercepts the request and `AdminUsersPage` lacks a client-side redirect hook, the browser renders the team members table and admin layout. When navigating to `/admin/dashboard`, the page displays the admin dashboard shell before `useEffect` redirects to `/login`.

**User/Data Impact:**  
Confusing user experience (flash of protected layout), exposure of client-side mock workflows on unguarded routes, and inefficient client execution. No backend legal data or PII is leaked.

**Security Impact:**  
Weakened defense-in-depth at the presentation layer; failure to enforce pre-hydration HTTP redirects at the server/edge boundary.

**Existing Mitigation:**  
FastAPI backend strictly enforces RBAC on all data-fetching endpoints (`/api/v1/admin/*`), returning 401/403 for unauthorized requests.

**Missing Control:**  
Implement Next.js `middleware.ts` to inspect session cookies and issue server-side redirects (HTTP 307) before page delivery for protected path prefixes (`/admin/:path*`, `/cases/:path*`, `/consultations/:path*`).

**Test Coverage:**  
`tests/integration/test_full_spectrum_security_hardening.py` verifies backend role authorization, but no test checks server-side route redirect behavior.

**Related Phase 1 Finding:** `AUTHZ-RBAC-01` (Role-Based Access Control)  
**Related Phase 2 Finding:** None  
**Related Phase 3 Finding:** None  

---

### Finding ID: FE-FIND-05
**Severity:** MEDIUM  
**Classification:** [VERIFIED]  
**Title:** Multiple API Contract Mismatches and Dead Code in Frontend API Layer  

**Affected Frontend Area:** API Client Layer / Domain Endpoints  

**Exact File(s):**  
- `frontend/src/lib/api/auth.ts`  
- `frontend/src/lib/api/verification.ts`  
- `frontend/src/lib/api/cases.ts`  
- `frontend/src/lib/api/documents.ts`  
- `frontend/src/lib/api/payments.ts`  
- `frontend/src/app/cases/[caseId]/bundles/page.tsx`  

**Exact Function/Component/Hook:**  
- `authApi.verifyEmail` (`lib/api/auth.ts:55`)  
- `verificationApi.getQueue` (`lib/api/verification.ts:12`)  
- `verificationApi.getDetail` (`lib/api/verification.ts:17`)  
- `verificationApi.review` (`lib/api/verification.ts:26`)  
- `verificationApi.submitEnrollment` (`lib/api/verification.ts:33`)  
- `casesApi.getBrief` (`lib/api/cases.ts:58`)  
- `documentsApi.completeUpload` (`lib/api/documents.ts:37`)  
- `paymentsApi.createIntent` (`lib/api/payments.ts:14`)  
- `BundlesPage.loadData` (`app/cases/[caseId]/bundles/page.tsx:113`)  

**Backend Endpoint(s):**  
- `POST /api/v1/auth/email/verify/confirm`  
- `GET /api/v1/verification/admin/queue`  
- `GET /api/v1/verification/admin/{id}`  
- `POST /api/v1/admin/verifications/{id}/approve` & `/reject`  
- `POST /api/v1/verification/application/submit`  
- `GET /api/v1/cases/{case_id}/collaboration/brief`  
- `POST /api/v1/cases/{case_id}/documents/{document_id}/complete`  
- `POST /api/v1/consultations/{consultation_id}/payments`  
- `GET /api/v1/cases/{case_id}/exhibits`  

**Evidence:**  
Cross-referencing the 407 backend endpoints from Phase 0/1 against `frontend/src/lib/api/` and active page components identified **9 explicit path/route contract mismatches** (8 in `lib/api/` helpers + 1 in a live page component):
1. `MISMATCH-01` (`lib/api/auth.ts:55`): `POST /api/v1/auth/verify-email`. Backend contract is `POST /api/v1/auth/email/verify/confirm` (`app/api/v1/auth.py:442`). Helper yields 404.
2. `MISMATCH-02` (`lib/api/verification.ts:12`): `GET /api/v1/admin/verification/queue`. Backend path is `GET /api/v1/verification/admin/queue` (`app/api/v1/verification.py:166`). Live admin pages bypass this helper and query `/api/v1/admin/verifications`.
3. `MISMATCH-03` (`lib/api/verification.ts:17`): `GET /api/v1/admin/verification/${verificationId}`. Backend path is `GET /api/v1/verification/admin/{id}` (`app/api/v1/verification.py:197`). Helper yields 404.
4. `MISMATCH-04` (`lib/api/verification.ts:26`): `POST /api/v1/admin/verification/${verificationId}/review`. Backend separates review into distinct `/approve` and `/reject` endpoints (`app/api/v1/admin.py:165`, `verification.py:247`). Helper yields 404.
5. `MISMATCH-05` (`lib/api/verification.ts:33`): `POST /api/v1/lawyers/me/verification`. Backend enrollment submission is `POST /api/v1/verification/application/submit` (`app/api/v1/verification.py:117`). Helper yields 404.
6. `MISMATCH-06` (`lib/api/cases.ts:58`): `GET /api/v1/cases/${caseId}/brief`. Backend path is `GET /api/v1/cases/{case_id}/collaboration/brief` (`app/api/v1/cases.py:446`). Helper yields 404.
7. `MISMATCH-07` (`lib/api/documents.ts:37`): `POST /api/v1/cases/${caseId}/documents/${documentId}/upload-complete`. Backend path is `POST /api/v1/cases/{case_id}/documents/{document_id}/complete` (`app/api/v1/documents.py:271`). Helper yields 404.
8. `MISMATCH-08` (`lib/api/payments.ts:14`): `POST /api/v1/consultations/${consultationId}/payment-intent`. Backend route is `POST /api/v1/consultations/{consultation_id}/payments` (`app/api/v1/consultations.py:756`). Helper yields 404.
9. `MISMATCH-09` (`app/cases/[caseId]/bundles/page.tsx:113`): `GET /api/v1/cases/${caseId}/evidence/exhibits`. Backend exhibits route is `GET /api/v1/cases/{case_id}/exhibits` (`app/api/v1/evidence.py:619`). In `bundles/page.tsx`, the superfluous `/evidence` segment causes an HTTP 404 error that is caught by lines 115–118, silently resetting `availableExhibits` to empty in the live bundles UI.

*(Note: Additionally, two testing bypass parameters in production pages are cataloged as `MISMATCH-10` in `FE-FIND-01` and `MISMATCH-11` in `FE-FIND-02`, bringing total identified contract discrepancies to 11).*

**Failure Scenario:**  
- **Helper Code:** A developer imports `verificationApi.getQueue()`, `paymentsApi.createIntent()`, or `casesApi.getBrief()`. At runtime, the API client issues an HTTP request to the mismatched path and receives an HTTP 404 Not Found response, crashing the calling feature.
- **Live Page (`MISMATCH-09`):** A user navigates to `/cases/[caseId]/bundles` to create an evidentiary court bundle. The page attempts to fetch exhibits via `/api/v1/cases/${caseId}/evidence/exhibits`. The backend returns 404. The catch handler executes `setAvailableExhibits([])`. The user sees an empty exhibits list and cannot link exhibits to bundles.

**User/Data Impact:**  
Exhibits are unavailable in the case bundles UI; helper library functions are broken and unmaintained, requiring inline string endpoint duplication.

**Security Impact:**  
Code maintenance debt and architectural divergence between frontend client abstractions and authoritative backend REST contracts.

**Existing Mitigation:**  
Most page components bypass the broken `lib/api/` helpers and call `apiClient.get/post` with direct inline strings.

**Missing Control:**  
Reconcile all endpoint strings in `frontend/src/lib/api/` and `bundles/page.tsx` against the backend OpenAPI contract. Implement automated contract tests to prevent endpoint drift.

**Test Coverage:**  
`tests/integration/test_phase_8_frontend_contracts.py` tests active endpoints, but does not test the dead helpers in `lib/api/` or `bundles/page.tsx`.

**Related Phase 1 Finding:** None  
**Related Phase 2 Finding:** None  
**Related Phase 3 Finding:** `BL-FIND-07` (Router/Service Logic Fragmentation)  

---

### Finding ID: FE-FIND-06
**Severity:** LOW  
**Classification:** [VERIFIED]  
**Title:** Plaintext Storage of Access and Refresh Tokens in Browser `sessionStorage`  

**Affected Frontend Area:** Session Management / Authentication  

**Exact File(s):**  
- `frontend/src/api/session.ts`  
- `frontend/src/api/client.ts`  

**Exact Function/Component/Hook:**  
- `setSessionAccessToken` (lines 63–72)  
- `setSessionRefreshToken` (lines 90–97)  
- `fetchWithAuth` (lines 202–225)  

**Backend Endpoint(s):**  
- `POST /api/v1/auth/login`  
- `POST /api/v1/auth/refresh`  

**Evidence:**  
In `frontend/src/api/session.ts`, both JWT access tokens and long-lived refresh tokens are stored in the browser's `sessionStorage`:
```typescript
const ACCESS_TOKEN_KEY = "lcc_access_token";
const REFRESH_TOKEN_KEY = "lcc_refresh_token";

export function setSessionAccessToken(token: string): void {
  sessionStorage.setItem(ACCESS_TOKEN_KEY, token);
}
export function setSessionRefreshToken(token: string): void {
  sessionStorage.setItem(REFRESH_TOKEN_KEY, token);
}
```
In `fetchWithAuth`:
```typescript
const token = getSessionAccessToken();
if (token) {
  headers.set("Authorization", `Bearer ${token}`);
}
```

**Failure Scenario:**  
A Cross-Site Scripting (XSS) vulnerability or malicious browser extension executes within the application origin. The attacker executes `sessionStorage.getItem('lcc_refresh_token')` and `sessionStorage.getItem('lcc_access_token')`, exfiltrating the credentials to an external server. With the refresh token, the attacker can establish persistent sessions even after the user closes the tab.

**User/Data Impact:**  
Potential account takeover and unauthorized access to privileged legal documents if an XSS attack occurs.

**Security Impact:**  
Subverts the protection of HttpOnly cookies; exposing refresh tokens to JavaScript execution environments.

**Existing Mitigation:**  
Session storage is partitioned per tab (unlike `localStorage`), reducing multi-tab leakage; tokens are purged on explicit logout.

**Missing Control:**  
Rely exclusively on backend `HttpOnly; Secure; SameSite=Strict` cookies for refresh token transmission, eliminating the need to store refresh tokens in client `sessionStorage`.

**Test Coverage:**  
`tests/security/test_full_spectrum_security_hardening.py` checks cookie headers, but does not assert absence of tokens in client storage.

**Related Phase 1 Finding:** `AUTH-SESS-01` (Session Token Transport)  
**Related Phase 2 Finding:** None  
**Related Phase 3 Finding:** None  

---

### Finding ID: FE-FIND-07
**Severity:** LOW  
**Classification:** [VERIFIED]  
**Title:** Silent Error Masking via `.catch(() => null)` in Critical Dashboard and Collaboration Queries  

**Affected Frontend Area:** Dashboard Overview / Case Workspace  

**Exact File(s):**  
- `frontend/src/app/dashboard/page.tsx`  
- `frontend/src/app/cases/[caseId]/page.tsx`  

**Exact Function/Component/Hook:**  
- `Dashboard.fetchDashboardData` (lines 100–104, 153, 167)  

**Backend Endpoint(s):**  
- `GET /api/v1/cases`  
- `GET /api/v1/consultations`  
- `GET /api/v1/calendar/events`  
- `GET /api/v1/cases/{id}/collaboration/brief`  

**Evidence:**  
In `frontend/src/app/dashboard/page.tsx`, lines 100–104 load core overview data using `Promise.all`:
```typescript
const [casesRes, consultRes, calEventsRes] = await Promise.all([
  apiClient.get("/api/v1/cases").catch(() => ({ items: [] })),
  apiClient.get("/api/v1/consultations").catch(() => ({ items: [] })),
  apiClient.get("/api/v1/calendar/events?timeframe=upcoming").catch(() => ({ events: [] })),
]);
```
If any of these calls fail due to network disconnection, timeout, or backend 500 error, the error is swallowed and converted into an empty array.

**Failure Scenario:**  
A temporary network hiccup or database pool exhaustion causes `/api/v1/calendar/events` or `/api/v1/cases` to fail with HTTP 500. Instead of displaying a retry banner or alerting the user, the dashboard displays "0 Active Cases" and "No Upcoming Hearings". A client or advocate relying on the dashboard misses a court appearance or limitation deadline believing no hearings are scheduled.

**User/Data Impact:**  
Misleading UI state; users mistake backend service disruptions for genuine zero-data states.

**Security Impact:**  
Loss of error visibility and failure transparency in legal operations.

**Existing Mitigation:**  
Outer `try...catch` sets `fetchError` only if `Promise.all` itself throws, which is bypassed by individual `.catch()` handlers.

**Missing Control:**  
Differentiate between empty data (`200 OK with []`) and error states (`500 / 0 Network Failure`). Display distinct error banners with retry triggers when API calls fail.

**Test Coverage:**  
Puppeteer tests verify successful rendering, but do not test partial API outage states.

**Related Phase 1 Finding:** None  
**Related Phase 2 Finding:** None  
**Related Phase 3 Finding:** `BL-FIND-06` (Exception Swallowing Patterns)  

---

### Finding ID: FE-FIND-08
**Severity:** LOW  
**Classification:** [VERIFIED]  
**Title:** Content Security Policy Permits `'unsafe-inline'` for Script Execution in Production  

**Affected Frontend Area:** Security Headers / Next.js Configuration  

**Exact File(s):**  
- `frontend/next.config.ts`  

**Exact Function/Component/Hook:**  
- `nextConfig.headers` (lines 97–110)  

**Backend Endpoint(s):**  
- N/A (HTTP Response Header Configuration)  

**Evidence:**  
In `frontend/next.config.ts`, line 100 defines the production Content Security Policy header:
```typescript
"Content-Security-Policy",
value: [
  "default-src 'self'",
  process.env.NODE_ENV === "production"
    ? "script-src 'self' 'unsafe-inline'"
    : "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
...
```
`'unsafe-inline'` is explicitly enabled in production mode for scripts.

**Failure Scenario:**  
An injection flaw is introduced into a rich text or template rendering component. Because `'unsafe-inline'` is permitted by the browser CSP header, the browser executes the inline script block without blocking, negating CSP as a defense-in-depth layer.

**User/Data Impact:**  
Reduces browser-level mitigation against potential XSS attacks.

**Security Impact:**  
Weakened Content Security Policy posture for a sensitive legal technology application.

**Existing Mitigation:**  
React JSX auto-escapes interpolated variables, and DOM sinks are minimal (`dangerouslySetInnerHTML` occurs only once for static theme initialization).

**Missing Control:**  
Use cryptographic nonces (`'nonce-...'`) or hashes for Next.js inline scripts and remove `'unsafe-inline'` from production CSP.

**Test Coverage:**  
None.

**Related Phase 1 Finding:** `SEC-FIND-04` (Cache-Control and Security Header Configuration)  
**Related Phase 2 Finding:** None  
**Related Phase 3 Finding:** None  

---
