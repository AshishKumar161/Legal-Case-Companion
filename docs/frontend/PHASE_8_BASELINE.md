# Phase 8 Frontend Baseline Documentation

## 1. Executive Summary

This document establishes the verified baseline for the Legal Case Companion (LCC) frontend codebase at the beginning of Phase 8.

All measurements reflect the production state following the successful completion of Phase 7 (External Integrations & Infrastructure Provider Hardening).

---

## 2. Baseline Metrics Matrix

| Metric Category | Baseline Value | Description / Notes |
| :--- | :--- | :--- |
| **Total Source Files** | 140 files | Total files under `frontend/src` |
| **TypeScript / TSX** | 111 files | 6 `.ts` files, 105 `.tsx` files |
| **CSS Modules / Styles** | 27 files | Vanilla CSS modules and design system tokens |
| **Localization Files** | 2 files | `en-IN.json` (1.6 KB) and `hi-IN.json` (3.2 KB) |
| **App Router Routes** | 41 routes | Active page routes under `frontend/src/app` |
| **UI Components** | 59 components | 26 UI primitives (`components/ui`), 33 feature components |
| **Custom Hooks** | 2 hooks | `useAuth()` (`AuthProvider.tsx`), `useI18n()` (`I18nProvider.tsx`) |
| **API Client Modules** | 2 files | `api/client.ts` (10.1 KB), `api/session.ts` (4.4 KB) |
| **Direct API Client Callers** | 49 files | Components and pages importing `@/api/client` directly |
| **Context Providers** | 2 providers | `AuthProvider` (auth & session lifecycle), `I18nProvider` (localization) |
| **Raw `fetch()` Calls** | 6 occurrences | 4 direct PUTs to S3 presigned URLs, 2 non-presigned API calls |
| **`dangerouslySetInnerHTML`** | 0 occurrences | Zero unescaped or raw HTML injection in frontend |
| **Exposed Backend Secrets** | 0 occurrences | Only `NEXT_PUBLIC_API_URL` and internal SSR variables used |
| **ESLint Baseline** | 0 errors, 31 warnings | Warnings caused by unused imports/vars and raw `<img>` tags |
| **TypeScript Baseline** | 0 errors | Clean compilation with `npx tsc --noEmit` |
| **Next.js Production Build** | PASS | 36/36 static/dynamic routes prerendered |
| **Backend Test Baseline** | 833 / 833 PASS | Pytest suite (including 129 security tests) |

---

## 3. Inventory of Next.js App Router Routes (41 Routes)

### Public & Informational Routes (4)
1. `/` (`app/page.tsx`): Hero landing page, feature highlights, trust indicators, direct advocate search.
2. `/design-system` (`app/design-system/page.tsx`): Visual component library showcase and token reference.
3. `/trust` (`app/trust/page.tsx`): Security, encryption, and confidentiality governance page.
4. `/support` (`app/support/page.tsx`): Help center, incident reporting, and user support ticketing.

### Authentication & Account Security Routes (6)
5. `/login` (`app/login/page.tsx`): Session login with email/password and Google OAuth 2.0.
6. `/register` (`app/register/page.tsx`): Role-aware account creation (Client vs. Advocate).
7. `/forgot-password` (`app/forgot-password/page.tsx`): Password reset request with rate-limiting.
8. `/reset-password` (`app/reset-password/page.tsx`): Secure tokenized password reset.
9. `/verify-email` (`app/verify-email/page.tsx`): Email confirmation link handler.
10. `/auth/callback` (`app/auth/callback/page.tsx`): OAuth 2.0 redirect target, state validator, and JWT session bootstrap.

### User Onboarding Routes (3)
11. `/onboarding` (`app/onboarding/page.tsx`): Onboarding router redirecting based on user role.
12. `/onboarding/advocate` (`app/onboarding/advocate/page.tsx`): Advocate profile, Bar Council enrollment, jurisdiction setup.
13. `/onboarding/client` (`app/onboarding/client/page.tsx`): Client profile, legal concern categorization, and introductory intake.

### Primary User Workspaces (8)
14. `/dashboard` (`app/dashboard/page.tsx`): Client centralized matter dashboard, attention items, upcoming hearings.
15. `/lawyer/dashboard` (`app/lawyer/dashboard/page.tsx`): Advocate operational command center, caseload metrics, upcoming consultations.
16. `/calendar` (`app/calendar/page.tsx`): Hearing dates, consultation slots, statutory limitation deadlines.
17. `/messages` (`app/messages/page.tsx`): Matter-scoped messaging and client-advocate correspondence.
18. `/notifications` (`app/notifications/page.tsx`): System notifications, event stream, read/unread management.
19. `/settings` (`app/settings/page.tsx`): Account settings, notification preferences, security options.
20. `/profile` (`app/profile/page.tsx`): User profile details and credentials.
21. `/lawyer/profile` (`app/lawyer/profile/page.tsx`): Public advocate directory profile editor and credentials.

### Case Workspace Routes (7)
22. `/cases` (`app/cases/page.tsx`): Caseload directory, status filtering, and search.
23. `/cases/new` (`app/cases/new/page.tsx`): Case intake and matter creation wizard.
24. `/cases/[caseId]` (`app/cases/[caseId]/page.tsx`): Master case workspace (Overview, Messages, Hearings, Documents, People, Timeline, Copilot).
25. `/cases/[caseId]/bundles` (`app/cases/[caseId]/bundles/page.tsx`): Court bundle generation, indexing, pagination, exhibit compilation.
26. `/cases/[caseId]/evidence` (`app/cases/[caseId]/evidence/page.tsx`): Case evidence locker, custody verification, categorization.
27. `/cases/[caseId]/evidence/[evidenceId]` (`app/cases/[caseId]/evidence/[evidenceId]/page.tsx`): Single evidence item inspection, versioning, chain of custody.
28. `/cases/[caseId]/timeline` (`app/cases/[caseId]/timeline/page.tsx`): Chronological case event timeline and statutory milestone tracking.

### Document & Evidence Workspace (1)
29. `/documents` (`app/documents/page.tsx`): Centralized document repository, virus scan status, category filtering, upload modal.

### Consultation & Video Room Routes (2)
30. `/consultations` (`app/consultations/page.tsx`): Scheduled, past, and pending video consultations list and booking.
31. `/consultations/[id]/room` (`app/consultations/[id]/room/page.tsx`): WebRTC / LiveKit video consultation room with document sharing, whiteboard, recording, and chat.

### Lawyer Directory & Booking (2)
32. `/lawyers` (`app/lawyers/page.tsx`): Verified advocate marketplace, search, fee filters, court filters.
33. `/lawyers/[lawyerId]` (`app/lawyers/[lawyerId]/page.tsx`): Advocate detail page with consultation slot selection and booking.

### Court Tracking & Payments (2)
34. `/court-tracking` (`app/court-tracking/page.tsx`): eCourts CNR case tracker, daily causelist monitoring, court orders.
35. `/payments` (`app/payments/page.tsx`): Invoices, consultation fee payments, refund requests, receipt downloads.

### Administrator Console Routes (5)
36. `/admin` (`app/admin/page.tsx`): Admin redirection gateway.
37. `/admin/dashboard` (`app/admin/dashboard/page.tsx`): Platform metrics, user statistics, system health.
38. `/admin/users` (`app/admin/users/page.tsx`): User account management, suspension, role assignment.
39. `/admin/reports` (`app/admin/reports/page.tsx`): Audit logs, compliance reports, revenue telemetry.
40. `/admin/verification` (`app/admin/verification/page.tsx`): Advocate Bar Council enrollment verification queue and approval.

### Catch-All / Error (1)
41. `_not-found` (Default Next.js 404 page, to be upgraded to branded `app/not-found.tsx`).

---

## 4. Component Duplication & Consolidation Baseline

### Duplicate Candidates Identified
1. **`components/EmptyState.tsx`** (87 lines) vs. **`components/ui/EmptyState.tsx`** (111 lines)
   - *Status*: Two separate EmptyState implementations. `components/ui/EmptyState.tsx` includes accessible ARIA markup (`aria-hidden="true"`), design system tokens, and `Button` primitives.
   - *Action*: Consolidate by having `components/EmptyState.tsx` adapt and re-export the enhanced `components/ui/EmptyState.tsx`.

2. **`components/LoadingSkeleton.tsx`** (78 lines) vs. **`components/ui/Skeleton.tsx`** (106 lines)
   - *Status*: Two skeleton loaders. `components/ui/Skeleton.tsx` includes `role="status"`, `aria-busy="true"`, `aria-label="Loading content..."`, and `@media (prefers-reduced-motion: reduce)`.
   - *Action*: Consolidate by having `components/LoadingSkeleton.tsx` adapt and delegate to `components/ui/Skeleton.tsx`.

3. **`components/StatusBadge.tsx`** (79 lines) vs. **`components/ui/Badge.tsx`** (100 lines) & **`components/ui/StatusChip.tsx`**
   - *Status*: `StatusBadge` is bound to `canonicalStatus.ts` legal status definitions (`OPEN`, `IN_REVIEW`, `QUARANTINED`, `STATUTORY_LIMITATION`). `Badge` is a generic UI token primitive.
   - *Action*: KEEP both with distinct responsibilities (domain legal status vs generic UI badge).

### Audited Standalone Components with 0 Direct References
1. **`components/ActionCenter/ActionCenter.tsx`** (801 lines): Full Action Center with task/hearing queues, case plan, and decision records. -> **KEEP & REUSE**.
2. **`components/Collaboration/MatterBriefCard.tsx`** (128 lines): Formatted brief card. -> **KEEP & REUSE** by rendering in `/cases/[caseId]/page.tsx` Overview tab.
3. **`components/Collaboration/MatterParticipantsPanel.tsx`** (139 lines): Participant directory with roles. -> **KEEP & REUSE** by rendering in `/cases/[caseId]/page.tsx` People tab.
4. **`components/Collaboration/MatterRequestsBoard.tsx`** (796 lines): Document request Kanban board. -> **KEEP & REUSE** in `/cases/[caseId]/page.tsx` Documents tab.
5. **`components/Intelligence/IntelligenceCenter.tsx`** (518 lines): Intelligence center with hybrid authority search, evidence matrix, and entity graph. -> **KEEP & REUSE**.

---

## 5. Current Warnings Baseline (31 Warnings)

- **Unused variables / imports (23 warnings)**:
  - `calendar/page.tsx:10:3`: 'CheckCircleIcon'
  - `cases/[caseId]/page.tsx:191:10`: 'linkedCourtCase'
  - `cases/[caseId]/page.tsx:586:9`: 'nextDeadline'
  - `cases/[caseId]/page.tsx:599:9`: 'openTasks'
  - `consultations/[id]/room/page.tsx:855:15`: 'pingInterval'
  - `dashboard/page.tsx:23:3`: 'DocumentIcon'
  - `dashboard/page.tsx:28:3`: 'CheckCircleIcon'
  - `documents/page.tsx:8:3`: 'UploadIcon'
  - `documents/page.tsx:12:3`: 'ArrowRightIcon'
  - `documents/page.tsx:17:8`: 'Link'
  - `documents/page.tsx:102:10`: 'sharedDocuments'
  - `documents/page.tsx:103:10`: 'pendingRequests'
  - `lawyers/[lawyerId]/page.tsx:45:10`: 'slots'
  - `lawyers/[lawyerId]/page.tsx:46:10`: 'loadingSlots'
  - `lawyers/[lawyerId]/page.tsx:47:10`: 'selectedSlot'
  - `lawyers/page.tsx:168:31`: 'setShowAdvancedFilters'
  - `page.tsx:6:3`: 'ScalesIcon'
  - `AppShell/Sidebar.tsx:8:3`: 'ScalesIcon'
  - `AppShell/TopBar.tsx:24:10`: 'istTime'
  - `Intelligence/CopilotChat.tsx:13:10`: 'TemporalValidityBadge'
  - `Intelligence/CopilotChat.tsx:17:3`: 'CheckCircleIcon'
  - `Intelligence/CopilotChat.tsx:18:3`: 'DocumentIcon'
  - `Intelligence/CopilotChat.tsx:19:3`: 'LawyerIcon'
  - `Navbar.tsx:7:10`: 'ScalesIcon'

- **Image element optimization (8 warnings)**:
  - `consultations/[id]/room/page.tsx:2354:15`: `<img>`
  - `login/page.tsx:181:13`: `<img>`
  - `page.tsx:27:15`: `<img>`
  - `register/page.tsx:257:17`: `<img>`
  - `AppShell/Sidebar.tsx:139:15`: `<img>`
  - `Intelligence/CopilotChat.tsx:207:13`: `<img>`
  - `Navbar.tsx:88:13`: `<img>`
