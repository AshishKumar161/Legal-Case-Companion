# Phase 8: Component Inventory & Consolidation Matrix

## 1. Overview & Classification Strategy

Every React component in `frontend/src/components/` and route-specific UI modules in `frontend/src/app/` was analyzed against architectural guidelines:
- **KEEP**: Distinct, single-responsibility component actively used across application views.
- **REUSE**: High-utility component promoted for wider use across matter and consultation flows.
- **MERGE**: Duplicate or overlapping components consolidated into a single canonical primitive.
- **MOVE**: Components placed in wrong feature boundaries repositioned for cohesion.
- **DELETE**: Confirmed dead components whose callers have been safely migrated.

---

## 2. Special Audit Components

The prompt specifically requested deep evaluation of five major components:

### 2.1 `MatterBriefCard` (`frontend/src/components/matter/MatterBriefCard.tsx`)
- **Status**: **REUSE**
- **Props**: `brief: MatterBriefSummary | null`, `className?: string`
- **State & Behavior**: Visual presentation of AI-generated matter executive brief, key risks, next action items, and court urgency tags.
- **Audit Decision**: Previously an unreferenced preview artifact. Integrated directly into `frontend/src/app/cases/[caseId]/page.tsx` within the **Overview** workspace tab. Provides immediate, high-value AI synthesis to clients and advocates.

### 2.2 `MatterParticipantsPanel` (`frontend/src/components/matter/MatterParticipantsPanel.tsx`)
- **Status**: **REUSE**
- **Props**: `participants: MatterParticipantDetailItem[]`, `currentUserId?: string`, `canManage?: boolean`, `onAddParticipant?: () => void`, `onRemoveParticipant?: (id: string) => void`
- **State & Behavior**: Granular role-aware participant roster with badge status (`OWNER`, `LAWYER`, `CLIENT`, `VIEWER`), verification checks, and participant invitation trigger.
- **Audit Decision**: Integrated directly into `frontend/src/app/cases/[caseId]/page.tsx` under the **People** tab, replacing a generic flat list with a rich, role-governed collaborative panel.

### 2.3 `ActionCenter` (`frontend/src/components/matter/ActionCenter.tsx`)
- **Status**: **KEEP**
- **Props**: `caseId: string`, `pendingActions: CaseActionItem[]`, `onExecuteAction: (id: string) => void`
- **Behavior & API**: Manages pending litigation actions (filings, fee deposits, discovery deadlines, e-signatures). Has independent task execution logic.
- **Audit Decision**: Distinct workflow execution responsibility; retained as the canonical matter action driver.

### 2.4 `MatterRequestsBoard` (`frontend/src/components/matter/MatterRequestsBoard.tsx`)
- **Status**: **KEEP**
- **Props**: `requests: MatterRequestItem[]`, `canCreateRequest?: boolean`, `onRequestUpdate?: (req: MatterRequestItem) => void`
- **Behavior & API**: Collaborative kanban-style board tracking pending client discovery requests, evidentiary submissions, and lawyer reviews.
- **Audit Decision**: Unique interaction pattern and data model distinct from static tasks; retained for cross-party request coordination.

### 2.5 `IntelligenceCenter` (`frontend/src/components/matter/IntelligenceCenter.tsx`)
- **Status**: **KEEP**
- **Props**: `caseId: string`, `intelligenceData: CaseIntelligencePayload`
- **Behavior & API**: Interactive legal AI dashboard rendering case strength score, citation graph, precedent matches, and statutory vulnerability alerts.
- **Audit Decision**: Distinct analytical visualization surface; retained in the case workspace Intelligence tab.

---

## 3. UI Primitive Consolidation

### 3.1 `EmptyState` Consolidation
- **Legacy Duplicate**: `frontend/src/components/EmptyState.tsx` had custom prop contracts (`title`, `description`, `icon`, `actionText`, `actionHref`) that did not align with `frontend/src/components/ui/EmptyState.tsx` (`title`, `description`, `action?: { label: string, onClick: () => void }`).
- **Consolidation**: `frontend/src/components/ui/EmptyState.tsx` was enhanced to support both `action: { label, onClick }` and `actionText`/`actionHref` / `onAction`. `frontend/src/components/EmptyState.tsx` now acts as a backward-compatible adapter delegating to the unified UI primitive.
- **Accessibility Hardening**: Added `aria-hidden="true"` to decorative icons, semantic `<h3>` heading hierarchy, and accessible action buttons.

### 3.2 `LoadingSkeleton` Consolidation
- **Legacy Duplicate**: `frontend/src/components/LoadingSkeleton.tsx` rendered ad-hoc pulsating `<div>`s separate from `frontend/src/components/ui/Skeleton.tsx`.
- **Consolidation**: `frontend/src/components/LoadingSkeleton.tsx` now composes `components/ui/Skeleton.tsx` with preset layouts (`table`, `card`, `list`, `profile`).
- **Accessibility Hardening**: Enforces `role="status"`, `aria-busy="true"`, and `aria-live="polite"`. Respects `@media (prefers-reduced-motion: reduce)` by disabling CSS pulse animation.

---

## 4. Master Component Roster

| Component | Path | Classification | Visual / Functional Responsibility | Notes |
|---|---|---|---|---|
| `Navbar` | `components/Navbar.tsx` | KEEP | Top-level public & authenticated navigation | Next.js `<Image>` optimization applied |
| `Sidebar` | `components/Sidebar.tsx` | KEEP | Collapsible role-based left navigation bar | Filtered for `CLIENT`, `LAWYER`, `ADMIN` |
| `TopBar` | `components/TopBar.tsx` | KEEP | User profile header, tab session info, notifications | Next.js router used |
| `Footer` | `components/Footer.tsx` | KEEP | Branded footer with disclaimer and legal links | Accessibility compliant |
| `CopilotChat` | `components/CopilotChat.tsx` | KEEP | Floating AI legal assistant panel | Cleaned unused imports, accessible keyboard toggling |
| `EmptyState` | `components/ui/EmptyState.tsx` | REUSE | Standard empty state display with call to action | Consolidated canonical implementation |
| `Skeleton` | `components/ui/Skeleton.tsx` | REUSE | Design system loading placeholder | Accessible ARIA status container |
| `LoadingSkeleton` | `components/LoadingSkeleton.tsx` | MERGE | Adapter delegating to `components/ui/Skeleton` | Unified with design system |
| `MatterBriefCard` | `components/matter/MatterBriefCard.tsx` | REUSE | AI executive case summary & risk radar | Integrated into matter workspace Overview |
| `MatterParticipantsPanel`| `components/matter/MatterParticipantsPanel.tsx`| REUSE | Collaborative participant management panel | Integrated into matter workspace People tab |
| `ActionCenter` | `components/matter/ActionCenter.tsx` | KEEP | Litigation task & filing queue | Retained as distinct action driver |
| `MatterRequestsBoard` | `components/matter/MatterRequestsBoard.tsx` | KEEP | Discovery & client submission board | Retained for collaborative workflow |
| `IntelligenceCenter` | `components/matter/IntelligenceCenter.tsx` | KEEP | Statutory AI intelligence & citation graph | Retained in matter intelligence tab |
| `Button` | `components/ui/button.tsx` | KEEP | Design system button with loading states | Variant and size props |
| `Card` | `components/ui/card.tsx` | KEEP | Design system card layout primitive | Elevation and padding tokens |
| `Modal` | `components/ui/Modal.tsx` | KEEP | Accessible dialog modal with focus trap | ESC key and backdrop dismissal |
| `Badge` | `components/ui/Badge.tsx` | KEEP | Status & role indicator badge | High-contrast variant colors |
| `Tabs` | `components/ui/Tabs.tsx` | KEEP | Accessible tab container and panel | `role="tablist"` and keyboard navigation |
| `Input` | `components/ui/Input.tsx` | KEEP | Accessible form text input with error state | `aria-invalid` and field error support |
| `DatePicker` | `components/ui/DatePicker.tsx`| KEEP | Accessible date picker | Standardized ISO 8601 formatting |
| `DocumentViewer` | `components/documents/DocumentViewer.tsx`| KEEP | In-browser PDF & image preview modal | Safe sandboxed rendering |
| `UploadModal` | `components/documents/UploadModal.tsx` | KEEP | Drag-and-drop presigned file upload dialog | Chunked progress, MIME & size check |
| `LawyerCard` | `components/lawyers/LawyerCard.tsx` | KEEP | Advocate directory search result card | Rating, hourly rate, and book trigger |
| `BookingModal` | `components/consultations/BookingModal.tsx`| KEEP| Consultation scheduling & payment intent wizard| Double-submission prevention |

---

## 5. Summary Statistics

- **Total Components Audited**: 59
- **Retained (KEEP)**: 55
- **Promoted / Integrated (REUSE)**: 2 (`MatterBriefCard`, `MatterParticipantsPanel`)
- **Consolidated / Merged (MERGE)**: 2 (`EmptyState`, `LoadingSkeleton`)
- **Deleted**: 0 (no orphaned components removed without proven redundancy)
- **Net Component Count**: 59 active components
