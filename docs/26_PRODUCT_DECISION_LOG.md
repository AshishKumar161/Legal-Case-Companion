# Legal Case Companion (LCC) — Product Decision Log & Roadmap (7.0)

This document formalizes the **Keep / Improve / Deprioritize** product decisions derived from controlled pilot evidence, establishing an evidence-driven product roadmap.

---

## 1. Feature Classification Matrix

### [KEEP] High Value, Actively Adopted
- **Matter Workspace & Brief KPIs**: Immediate matter overview gives clients and counsel instant situational awareness.
- **Grounded Copilot 2.0 (Dual-Source)**: Users highly value verified statutory citations and grounded fact extraction.
- **Matter Collaboration & Requests**: Structured request-to-submission loop (`PENDING` $\to$ `SUBMITTED` $\to$ `REVIEWED`) replaces fragmented WhatsApp/email threads.
- **Human Decision Register**: Essential for advocate governance, auditability, and professional accountability.

### [IMPROVE] Valuable but Needs Friction Reduction
- **Mobile Request Submission**: Improve file upload touch targets on mobile viewports for clients on the move.
- **Limitation Tracking UI**: Provide visual countdown chips for critical court limitation deadlines (e.g. *Section 34 Arbitration challenge 90-day window*).
- **Statutory Authority Search**: Add quick filter for Supreme Court vs High Court precedents in Legal Authority matrix.

### [DEPRIORITIZE] Not Currently Justified by Evidence
- **Generic AI Legal Chatbot without Context**: Pilot evidence shows generic AI chat creates confusion; users only trust matter-grounded insights.
- **Social Lawyer Feed / Ratings**: Advocates rejected public rating widgets; legal representation selection relies on verifiable bar credentials and fee transparency.
- **Gamification Badges**: Inappropriate for serious commercial legal proceedings.

---

## 2. Post-Pilot Release Roadmap

1. **Sprint 7.1 (Mobile Refinement Pass)**:
   - Optimize touch targets on `MatterRequestsBoard.tsx` and `DocumentUploadModal.tsx`.
2. **Sprint 7.2 (Proactive Limitation Radar)**:
   - Surface limitation warnings 14 days before critical statutory cutoff directly in TopBar alerts.
3. **Sprint 7.3 (Client Invoicing Integration)**:
   - Provide GST-compliant tax invoices for advocate consultation fees.
